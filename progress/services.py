"""
Progression engine for RoadmapLearn (service layer, no views).

Rules (see PROJECT_CONTEXT.md, "Progression rules"):
  * A node is COMPLETED only when the video check passed AND the quiz passed
    (or the node has no quiz and the video check passed).
  * Anti-cheat: the server never trusts client totals. Each heartbeat credits
    min(forward_delta, elapsed * playback_rate + tolerance) seconds.
  * Completing a node unlocks the next one (next higher ``order``).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Mapping, Optional

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from quizzes.models import Choice, QuizAttempt
from roadmaps.models import Node, Roadmap, Video

from .models import NodeProgress, RoadmapEnrollment, VideoProgress

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VIDEO_COMPLETION_THRESHOLD = 0.9
HEARTBEAT_TOLERANCE_SECONDS = 2.0
MAX_PLAYBACK_RATE = 2.0
MIN_PLAYBACK_RATE = 0.25
XP_PER_NODE_COMPLETED = 50


# ---------------------------------------------------------------------------
# Exceptions (views will translate these into responses later)
# ---------------------------------------------------------------------------
class ProgressError(Exception):
    """Base class for progression errors."""


class NodeLockedError(ProgressError):
    """The node is still LOCKED for this user."""


class NotEnrolledError(ProgressError):
    """The user is not enrolled in the node's roadmap."""


class VideoNotEmbeddableError(ProgressError):
    """The video cannot be embedded, so it cannot earn watch credit."""


class VideoCheckNotPassedError(ProgressError):
    """The user has not watched enough of the node's videos yet."""


class InvalidAnswerError(ProgressError):
    """Submitted answers do not match the node's quiz."""


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------
@transaction.atomic
def enroll_user(user, roadmap: Roadmap) -> RoadmapEnrollment:
    """
    Idempotently enroll ``user`` and create a NodeProgress for every node.

    The node with the lowest ``order`` is UNLOCKED, all others LOCKED.
    Existing NodeProgress rows are never modified (re-enrolling is safe).
    """
    enrollment, _ = RoadmapEnrollment.objects.get_or_create(user=user, roadmap=roadmap)
    nodes = list(roadmap.nodes.order_by("order", "pk"))
    for index, node in enumerate(nodes):
        defaults = {"status": NodeProgress.Status.LOCKED}
        if index == 0:
            defaults = {
                "status": NodeProgress.Status.UNLOCKED,
                "unlocked_at": timezone.now(),
            }
        NodeProgress.objects.get_or_create(user=user, node=node, defaults=defaults)
    return enrollment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _require_enrolled(user, roadmap: Roadmap) -> None:
    if not RoadmapEnrollment.objects.filter(user=user, roadmap=roadmap).exists():
        raise NotEnrolledError(f"{user} is not enrolled in {roadmap}.")


def _require_unlocked(user, node: Node) -> NodeProgress:
    """Return the NodeProgress, raising if missing or LOCKED."""
    progress = NodeProgress.objects.filter(user=user, node=node).first()
    if progress is None or progress.status == NodeProgress.Status.LOCKED:
        raise NodeLockedError(f"Node '{node.title}' is locked.")
    return progress


# ---------------------------------------------------------------------------
# Anti-cheat heartbeat
# ---------------------------------------------------------------------------
@transaction.atomic
def record_heartbeat(
    user,
    video: Video,
    current_time: float,
    playback_rate: float = 1.0,
    now: Optional[datetime] = None,
) -> VideoProgress:
    """
    Record a player heartbeat and credit genuinely-watched seconds.

    Raises NotEnrolledError, NodeLockedError, VideoNotEmbeddableError.

    * playback_rate is clamped to [MIN_PLAYBACK_RATE, MAX_PLAYBACK_RATE].
    * First heartbeat for user+video: stores position/time, credits 0.
    * Later: elapsed = now - last_heartbeat_at (>= 0); delta = current_time -
      last_position. delta <= 0 credits 0; otherwise
      credit = min(delta, elapsed * rate + HEARTBEAT_TOLERANCE_SECONDS).
    * watched_seconds never decreases and never exceeds video.duration_seconds.
      The column is an integer, so the credit is rounded to whole seconds.
    """
    now = now or timezone.now()
    node = video.node
    _require_enrolled(user, node.roadmap)
    _require_unlocked(user, node)
    if not video.is_embeddable:
        raise VideoNotEmbeddableError(f"Video '{video.title}' is not embeddable.")

    rate = max(MIN_PLAYBACK_RATE, min(MAX_PLAYBACK_RATE, float(playback_rate)))
    current_time = float(current_time)

    progress, _ = VideoProgress.objects.select_for_update().get_or_create(
        user=user, video=video
    )

    credit = 0
    if progress.last_heartbeat_at is not None:
        elapsed = max(0.0, (now - progress.last_heartbeat_at).total_seconds())
        delta = current_time - progress.last_position
        if delta > 0:
            raw = min(delta, elapsed * rate + HEARTBEAT_TOLERANCE_SECONDS)
            credit = int(raw + 0.5)

    new_total = progress.watched_seconds + credit
    progress.watched_seconds = max(
        progress.watched_seconds, min(new_total, video.duration_seconds)
    )
    progress.last_position = current_time
    progress.last_heartbeat_at = now
    progress.save(
        update_fields=["watched_seconds", "last_position", "last_heartbeat_at"]
    )
    return progress


# ---------------------------------------------------------------------------
# Video check
# ---------------------------------------------------------------------------
def video_check_passed(user, node: Node) -> bool:
    """
    True when sum(min(watched, duration)) over the node's EMBEDDABLE videos is
    >= VIDEO_COMPLETION_THRESHOLD * sum(their durations).

    A node with no embeddable videos (or zero total duration) passes
    automatically, since there is nothing the user can watch.
    """
    videos = list(node.videos.filter(is_embeddable=True))
    total = sum(v.duration_seconds for v in videos)
    if not videos or total == 0:
        return True
    watched_map = dict(
        VideoProgress.objects.filter(user=user, video__in=videos).values_list(
            "video_id", "watched_seconds"
        )
    )
    watched = sum(min(watched_map.get(v.pk, 0), v.duration_seconds) for v in videos)
    return watched >= VIDEO_COMPLETION_THRESHOLD * total - 1e-9


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------
def submit_quiz(user, node: Node, answers: Mapping[int, int]) -> QuizAttempt:
    """
    Grade a quiz submission. ``answers`` maps question_id -> choice_id.

    Raises NodeLockedError, VideoCheckNotPassedError, InvalidAnswerError.
    Unanswered questions count as wrong. Creates a QuizAttempt; if passed
    (score >= node.quiz_pass_mark) the node is completed. Correct choices are
    never exposed.
    """
    _require_unlocked(user, node)
    if not video_check_passed(user, node):
        raise VideoCheckNotPassedError("Watch the videos before taking the quiz.")

    quiz = getattr(node, "quiz", None)
    questions = list(quiz.questions.all()) if quiz else []
    if not questions:
        raise InvalidAnswerError("This node has no quiz questions.")

    question_ids = {q.pk for q in questions}
    chosen = {}
    for raw_q, raw_c in answers.items():
        try:
            q_id, c_id = int(raw_q), int(raw_c)
        except (TypeError, ValueError):
            raise InvalidAnswerError("Answers must be integer ids.")
        if q_id not in question_ids:
            raise InvalidAnswerError(f"Question {q_id} is not part of this quiz.")
        chosen[q_id] = c_id

    valid_choices = {
        (c.pk, c.question_id): c.is_correct
        for c in Choice.objects.filter(question__in=questions)
    }
    correct = 0
    for q_id, c_id in chosen.items():
        if (c_id, q_id) not in valid_choices:
            raise InvalidAnswerError(
                f"Choice {c_id} does not belong to question {q_id}."
            )
        if valid_choices[(c_id, q_id)]:
            correct += 1

    total = len(questions)
    score_percent = int(correct * 100 / total + 0.5)
    passed = correct * 100 >= node.quiz_pass_mark * total

    with transaction.atomic():
        attempt = QuizAttempt.objects.create(
            user=user, quiz=quiz, score_percent=score_percent, passed=passed
        )
        if passed:
            complete_node(user, node)
    return attempt


def try_complete_node_without_quiz(user, node: Node) -> bool:
    """
    Complete a node that has no quiz (or a quiz with no questions) once the
    video check passes. Returns True if the node is now COMPLETED, else False
    (node has quiz questions, or video check not passed).
    """
    _require_unlocked(user, node)
    quiz = getattr(node, "quiz", None)
    if quiz is not None and quiz.questions.exists():
        return False
    if not video_check_passed(user, node):
        return False
    complete_node(user, node)
    return True


# ---------------------------------------------------------------------------
# Completion, streak, progress
# ---------------------------------------------------------------------------
@transaction.atomic
def complete_node(user, node: Node) -> bool:
    """
    Mark the node COMPLETED (idempotent), unlock the next node if it is LOCKED,
    award XP exactly once and update the streak.

    Returns True when every node of the roadmap is now COMPLETED.
    """
    progress = (
        NodeProgress.objects.select_for_update().filter(user=user, node=node).first()
    )
    if progress is None or progress.status == NodeProgress.Status.LOCKED:
        raise NodeLockedError(f"Node '{node.title}' is locked.")

    if progress.status != NodeProgress.Status.COMPLETED:
        now = timezone.now()
        progress.status = NodeProgress.Status.COMPLETED
        progress.completed_at = now
        progress.save(update_fields=["status", "completed_at"])

        next_node = (
            node.roadmap.nodes.filter(order__gt=node.order).order_by("order").first()
        )
        if next_node is not None:
            nxt, _ = NodeProgress.objects.get_or_create(
                user=user,
                node=next_node,
                defaults={"status": NodeProgress.Status.UNLOCKED, "unlocked_at": now},
            )
            if nxt.status == NodeProgress.Status.LOCKED:
                nxt.status = NodeProgress.Status.UNLOCKED
                nxt.unlocked_at = now
                nxt.save(update_fields=["status", "unlocked_at"])

        type(user).objects.filter(pk=user.pk).update(xp=F("xp") + XP_PER_NODE_COMPLETED)
        user.refresh_from_db(fields=["xp"])
        update_streak(user)

    stats = roadmap_progress(user, node.roadmap)
    return stats["total"] > 0 and stats["completed"] == stats["total"]


def update_streak(user, today: Optional[date] = None) -> None:
    """
    Same day: no change. Yesterday: streak_days += 1. Otherwise: streak_days = 1.
    Always sets last_active_date to ``today``.
    """
    today = today or timezone.localdate()
    last = user.last_active_date
    if last == today:
        return
    if last is not None and last == today - timedelta(days=1):
        user.streak_days += 1
    else:
        user.streak_days = 1
    user.last_active_date = today
    user.save(update_fields=["streak_days", "last_active_date"])


def roadmap_progress(user, roadmap: Roadmap) -> dict:
    """Return {"completed": int, "total": int, "percent": int} for the roadmap."""
    total = roadmap.nodes.count()
    completed = NodeProgress.objects.filter(
        user=user, node__roadmap=roadmap, status=NodeProgress.Status.COMPLETED
    ).count()
    percent = int(completed * 100 / total) if total else 0
    return {"completed": completed, "total": total, "percent": percent}
