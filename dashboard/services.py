"""
Business-logic services for the dashboard app.
XP calculation, streak display, badge seeding/awarding, and dashboard summary data.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from django.utils import timezone

from notes.models import Note
from progress.models import NodeProgress, RoadmapEnrollment
from progress.services import node_statuses, roadmap_progress
from quizzes.models import QuizAttempt
from roadmaps.models import Node

from .models import Badge, UserBadge

BADGE_DEFINITIONS = [
    {
        "slug": "first_step",
        "name": "First Step",
        "description": "Complete your first topic.",
        "icon": "flag",
    },
    {
        "slug": "on_a_roll",
        "name": "On a Roll",
        "description": "Maintain a 3-day learning streak.",
        "icon": "flame",
    },
    {
        "slug": "week_warrior",
        "name": "Week Warrior",
        "description": "Maintain a 7-day learning streak.",
        "icon": "shield",
    },
    {
        "slug": "quiz_ace",
        "name": "Quiz Ace",
        "description": "Score 100% on a quiz.",
        "icon": "star",
    },
    {
        "slug": "roadmap_finisher",
        "name": "Roadmap Finisher",
        "description": "Complete every topic in a roadmap.",
        "icon": "trophy",
    },
    {
        "slug": "note_taker",
        "name": "Note Taker",
        "description": "Save personal notes on 5 topics.",
        "icon": "notebook",
    },
]


def ensure_badges_seeded() -> list[tuple[Badge, bool]]:
    """
    Idempotently create the 6 canonical Badge rows by slug (code).
    Returns a list of (Badge, created) pairs in canonical order.
    """
    results: list[tuple[Badge, bool]] = []
    for spec in BADGE_DEFINITIONS:
        badge, created = Badge.objects.get_or_create(
            slug=spec["slug"],
            defaults={
                "name": spec["name"],
                "description": spec["description"],
                "icon": spec["icon"],
            },
        )
        results.append((badge, created))
    return results


def effective_streak(user, today: Optional[date] = None) -> int:
    """
    Display-only streak helper: returns 0 if ``user.last_active_date`` is missing
    or before yesterday relative to ``today``, otherwise returns ``user.streak_days``.
    Never writes to the database.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return 0
    today = today or timezone.localdate()
    last = user.last_active_date
    if last is None or last < today - timedelta(days=1):
        return 0
    return int(user.streak_days)


def _has_completed_any_roadmap(user) -> bool:
    """True when every node of at least one non-empty roadmap is COMPLETED for user."""
    completed_roadmap_ids = (
        NodeProgress.objects.filter(
            user=user, status=NodeProgress.Status.COMPLETED
        )
        .values_list("node__roadmap_id", flat=True)
        .distinct()
    )
    for rm_id in completed_roadmap_ids:
        total_nodes = Node.objects.filter(roadmap_id=rm_id).count()
        if total_nodes == 0:
            continue
        done_nodes = NodeProgress.objects.filter(
            user=user,
            node__roadmap_id=rm_id,
            status=NodeProgress.Status.COMPLETED,
        ).count()
        if done_nodes == total_nodes:
            return True
    return False


def award_badges(user, today: Optional[date] = None) -> list[Badge]:
    """
    Evaluate all 6 badge rules for ``user`` and idempotently create ``UserBadge``
    rows for any newly earned badges.

    Returns the list of newly awarded ``Badge`` objects (empty on repeat calls).
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return []

    seeded = {badge.slug: badge for badge, _ in ensure_badges_seeded()}
    already_earned = set(
        UserBadge.objects.filter(user=user).values_list("badge__slug", flat=True)
    )

    completed_topics_count = NodeProgress.objects.filter(
        user=user, status=NodeProgress.Status.COMPLETED
    ).count()

    # Use effective_streak when last_active_date is set, or user.streak_days if
    # streak_days was set directly without last_active_date.
    if user.last_active_date is not None:
        current_streak = effective_streak(user, today=today)
    else:
        current_streak = int(user.streak_days)

    has_quiz_ace = QuizAttempt.objects.filter(
        user=user, score_percent__gte=100
    ).exists()

    has_finished_roadmap = (
        _has_completed_any_roadmap(user) if completed_topics_count > 0 else False
    )

    notes_count = (
        Note.objects.filter(user=user)
        .exclude(content="")
        .values("node_id")
        .distinct()
        .count()
    )

    earned_conditions = {
        "first_step": completed_topics_count >= 1,
        "on_a_roll": current_streak >= 3,
        "week_warrior": current_streak >= 7,
        "quiz_ace": has_quiz_ace,
        "roadmap_finisher": has_finished_roadmap,
        "note_taker": notes_count >= 5,
    }

    newly_awarded: list[Badge] = []
    for spec in BADGE_DEFINITIONS:
        slug = spec["slug"]
        if earned_conditions.get(slug) and slug not in already_earned:
            badge = seeded[slug]
            _, created = UserBadge.objects.get_or_create(user=user, badge=badge)
            if created:
                newly_awarded.append(badge)

    return newly_awarded


def get_dashboard_data(user, today: Optional[date] = None) -> dict:
    """
    Build the context dictionary for the student dashboard view.
    """
    ensure_badges_seeded()

    streak = effective_streak(user, today=today)
    topics_completed = NodeProgress.objects.filter(
        user=user, status=NodeProgress.Status.COMPLETED
    ).count()

    # Enrolled roadmaps ("Continue learning")
    enrollments = (
        RoadmapEnrollment.objects.filter(user=user)
        .select_related("roadmap__category")
        .order_by("-enrolled_at", "pk")
    )
    enrolled_roadmaps = []
    for enrollment in enrollments:
        rm = enrollment.roadmap
        prog = roadmap_progress(user, rm)
        statuses = node_statuses(user, rm)
        ordered_nodes = list(rm.nodes.order_by("order", "pk"))
        node_rows = [
            {"node": n, "status": statuses.get(n.pk, NodeProgress.Status.LOCKED)}
            for n in ordered_nodes
        ]
        next_unlocked_node = next(
            (
                row["node"]
                for row in node_rows
                if row["status"] == NodeProgress.Status.UNLOCKED
            ),
            None,
        )
        enrolled_roadmaps.append(
            {
                "roadmap": rm,
                "progress": prog,
                "nodes": node_rows,
                "next_node": next_unlocked_node,
            }
        )

    # Badges (earned with awarded_at date; unearned with how-to-earn description)
    user_badges_by_slug = {
        ub.badge.slug: ub
        for ub in UserBadge.objects.filter(user=user).select_related("badge")
    }
    badges_by_slug = {b.slug: b for b in Badge.objects.all()}
    badge_cards = []
    for spec in BADGE_DEFINITIONS:
        slug = spec["slug"]
        badge = badges_by_slug.get(slug)
        ub = user_badges_by_slug.get(slug)
        badge_cards.append(
            {
                "badge": badge,
                "slug": slug,
                "name": badge.name if badge else spec["name"],
                "description": (
                    badge.description
                    if badge and badge.description
                    else spec["description"]
                ),
                "icon": badge.icon if badge and badge.icon else spec["icon"],
                "earned": ub is not None,
                "awarded_at": ub.awarded_at if ub is not None else None,
            }
        )

    # Recent activity: last 8 events across completed nodes and quiz attempts
    completed_events = (
        NodeProgress.objects.filter(
            user=user,
            status=NodeProgress.Status.COMPLETED,
            completed_at__isnull=False,
        )
        .select_related("node__roadmap")
        .order_by("-completed_at")[:8]
    )
    quiz_events = (
        QuizAttempt.objects.filter(user=user)
        .select_related("quiz__node__roadmap")
        .order_by("-attempted_at")[:8]
    )

    events = []
    for np in completed_events:
        events.append(
            {
                "type": "node_completed",
                "timestamp": np.completed_at,
                "node": np.node,
                "roadmap": np.node.roadmap,
                "score_percent": None,
                "passed": True,
            }
        )
    for qa in quiz_events:
        events.append(
            {
                "type": "quiz_attempt",
                "timestamp": qa.attempted_at,
                "node": qa.quiz.node,
                "roadmap": qa.quiz.node.roadmap,
                "score_percent": qa.score_percent,
                "passed": qa.passed,
            }
        )

    events.sort(key=lambda e: e["timestamp"], reverse=True)
    recent_activity = events[:8]

    return {
        "xp": user.xp,
        "effective_streak": streak,
        "topics_completed": topics_completed,
        "enrolled_roadmaps": enrolled_roadmaps,
        "badges": badge_cards,
        "earned_badges_count": len(user_badges_by_slug),
        "recent_activity": recent_activity,
    }
