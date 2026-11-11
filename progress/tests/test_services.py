from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from progress import services
from progress.models import NodeProgress, RoadmapEnrollment, VideoProgress
from progress.services import (
    InvalidAnswerError,
    NodeLockedError,
    NotEnrolledError,
    VideoCheckNotPassedError,
    VideoNotEmbeddableError,
)
from quizzes.models import Choice, Question, Quiz, QuizAttempt
from roadmaps.models import Node, Roadmap, Video

User = get_user_model()
T0 = timezone.now().replace(microsecond=0)


def secs(n):
    return T0 + timedelta(seconds=n)


def make_node(roadmap, order, with_quiz=True, duration=300):
    node = Node.objects.create(
        roadmap=roadmap, title=f"Node {order}", slug=f"node-{order}", order=order
    )
    video = Video.objects.create(
        node=node, youtube_id=f"vid{order:08d}", title=f"Video {order}",
        duration_seconds=duration, order=1,
    )
    if with_quiz:
        quiz = Quiz.objects.create(node=node, title=f"Quiz {order}")
        for q in range(1, 4):
            question = Question.objects.create(quiz=quiz, text=f"Q{q}", order=q)
            Choice.objects.create(question=question, text="right", is_correct=True)
            Choice.objects.create(question=question, text="wrong", is_correct=False)
    return node, video


def answers(node, correct=True):
    """question_id -> choice_id, all right or all wrong."""
    result = {}
    for question in node.quiz.questions.all():
        choice = question.choices.get(is_correct=correct)
        result[question.pk] = choice.pk
    return result


class ProgressTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("student", password="x")
        self.roadmap = Roadmap.objects.create(title="R", slug="r")
        self.n1, self.v1 = make_node(self.roadmap, 1)
        self.n2, self.v2 = make_node(self.roadmap, 2)
        self.n3, self.v3 = make_node(self.roadmap, 3)
        services.enroll_user(self.user, self.roadmap)

    def status(self, node, user=None):
        return NodeProgress.objects.get(user=user or self.user, node=node).status

    def set_watched(self, video, seconds, user=None):
        VideoProgress.objects.update_or_create(
            user=user or self.user, video=video,
            defaults={"watched_seconds": seconds},
        )

    def watched(self, video):
        return VideoProgress.objects.get(user=self.user, video=video).watched_seconds


class EnrollTests(ProgressTestBase):
    def test_enroll_creates_rows_with_first_unlocked(self):
        self.assertEqual(RoadmapEnrollment.objects.count(), 1)
        self.assertEqual(NodeProgress.objects.filter(user=self.user).count(), 3)
        self.assertEqual(self.status(self.n1), NodeProgress.Status.UNLOCKED)
        self.assertEqual(self.status(self.n2), NodeProgress.Status.LOCKED)
        self.assertEqual(self.status(self.n3), NodeProgress.Status.LOCKED)

    def test_enroll_is_idempotent_and_keeps_progress(self):
        services.complete_node(self.user, self.n1)
        services.enroll_user(self.user, self.roadmap)
        self.assertEqual(RoadmapEnrollment.objects.count(), 1)
        self.assertEqual(NodeProgress.objects.filter(user=self.user).count(), 3)
        self.assertEqual(self.status(self.n1), NodeProgress.Status.COMPLETED)
        self.assertEqual(self.status(self.n2), NodeProgress.Status.UNLOCKED)


class HeartbeatTests(ProgressTestBase):
    def test_first_heartbeat_credits_zero(self):
        vp = services.record_heartbeat(self.user, self.v1, 100, now=T0)
        self.assertEqual(vp.watched_seconds, 0)
        self.assertEqual(vp.last_position, 100)
        self.assertEqual(vp.last_heartbeat_at, T0)

    def test_normal_playback_credits_elapsed(self):
        services.record_heartbeat(self.user, self.v1, 0, now=T0)
        vp = services.record_heartbeat(self.user, self.v1, 5, now=secs(5))
        self.assertEqual(vp.watched_seconds, 5)

    def test_forward_seek_credits_only_tolerance(self):
        services.record_heartbeat(self.user, self.v1, 0, now=T0)
        vp = services.record_heartbeat(self.user, self.v1, 200, now=secs(5))
        self.assertEqual(vp.watched_seconds, 7)  # 5s elapsed + 2s tolerance

    def test_rewind_credits_zero_and_never_reduces(self):
        services.record_heartbeat(self.user, self.v1, 0, now=T0)
        services.record_heartbeat(self.user, self.v1, 100, now=secs(100))
        self.assertEqual(self.watched(self.v1), 100)
        vp = services.record_heartbeat(self.user, self.v1, 50, now=secs(105))
        self.assertEqual(vp.watched_seconds, 100)
        self.assertEqual(vp.last_position, 50)

    def test_double_speed_credited_fairly(self):
        services.record_heartbeat(self.user, self.v1, 0, now=T0)
        vp = services.record_heartbeat(
            self.user, self.v1, 10, playback_rate=2.0, now=secs(5)
        )
        self.assertEqual(vp.watched_seconds, 10)

    def test_excessive_rate_is_clamped(self):
        services.record_heartbeat(self.user, self.v1, 0, now=T0)
        vp = services.record_heartbeat(
            self.user, self.v1, 100, playback_rate=10, now=secs(5)
        )
        self.assertEqual(vp.watched_seconds, 12)  # 5*2 + 2

    def test_watched_never_exceeds_duration(self):
        services.record_heartbeat(self.user, self.v1, 0, now=T0)
        services.record_heartbeat(self.user, self.v1, 290, now=secs(290))
        vp = services.record_heartbeat(self.user, self.v1, 600, now=secs(600))
        self.assertEqual(vp.watched_seconds, 300)

    def test_rejected_for_locked_node(self):
        with self.assertRaises(NodeLockedError):
            services.record_heartbeat(self.user, self.v2, 0, now=T0)

    def test_rejected_for_non_enrolled_user(self):
        other = User.objects.create_user("other", password="x")
        with self.assertRaises(NotEnrolledError):
            services.record_heartbeat(other, self.v1, 0, now=T0)

    def test_rejected_for_non_embeddable_video(self):
        self.v1.is_embeddable = False
        self.v1.save()
        with self.assertRaises(VideoNotEmbeddableError):
            services.record_heartbeat(self.user, self.v1, 0, now=T0)


class VideoCheckTests(ProgressTestBase):
    def test_threshold_boundary(self):
        self.set_watched(self.v1, 267)  # 89%
        self.assertFalse(services.video_check_passed(self.user, self.n1))
        self.set_watched(self.v1, 270)  # 90%
        self.assertTrue(services.video_check_passed(self.user, self.n1))

    def test_no_embeddable_videos_passes(self):
        self.v1.is_embeddable = False
        self.v1.save()
        self.assertTrue(services.video_check_passed(self.user, self.n1))

    def test_non_embeddable_videos_are_ignored(self):
        extra = Video.objects.create(
            node=self.n1, youtube_id="extra000000", title="x",
            duration_seconds=1000, order=2, is_embeddable=False,
        )
        self.set_watched(self.v1, 270)
        self.assertTrue(services.video_check_passed(self.user, self.n1))
        self.assertIsNotNone(extra.pk)


class QuizTests(ProgressTestBase):
    def test_quiz_rejected_before_video_check(self):
        with self.assertRaises(VideoCheckNotPassedError):
            services.submit_quiz(self.user, self.n1, answers(self.n1))
        self.assertEqual(QuizAttempt.objects.count(), 0)

    def test_quiz_rejected_on_locked_node(self):
        with self.assertRaises(NodeLockedError):
            services.submit_quiz(self.user, self.n2, answers(self.n2))

    def test_failing_quiz_keeps_state_and_stores_attempt(self):
        self.set_watched(self.v1, 300)
        attempt = services.submit_quiz(self.user, self.n1, answers(self.n1, False))
        self.assertFalse(attempt.passed)
        self.assertEqual(attempt.score_percent, 0)
        self.assertEqual(QuizAttempt.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.status(self.n1), NodeProgress.Status.UNLOCKED)
        self.assertEqual(self.status(self.n2), NodeProgress.Status.LOCKED)

    def test_unanswered_counts_wrong(self):
        self.set_watched(self.v1, 300)
        partial = dict(list(answers(self.n1).items())[:1])  # 1 of 3 right = 33%
        attempt = services.submit_quiz(self.user, self.n1, partial)
        self.assertEqual(attempt.score_percent, 33)
        self.assertFalse(attempt.passed)

    def test_passing_completes_and_unlocks_next(self):
        self.set_watched(self.v1, 300)
        attempt = services.submit_quiz(self.user, self.n1, answers(self.n1))
        self.assertTrue(attempt.passed)
        self.assertEqual(attempt.score_percent, 100)
        self.assertEqual(self.status(self.n1), NodeProgress.Status.COMPLETED)
        self.assertEqual(self.status(self.n2), NodeProgress.Status.UNLOCKED)
        self.assertEqual(self.status(self.n3), NodeProgress.Status.LOCKED)

    def test_choice_from_other_question_rejected(self):
        self.set_watched(self.v1, 300)
        q1, q2, _ = list(self.n1.quiz.questions.all())
        foreign = q2.choices.first()
        with self.assertRaises(InvalidAnswerError):
            services.submit_quiz(self.user, self.n1, {q1.pk: foreign.pk})
        self.assertEqual(QuizAttempt.objects.count(), 0)

    def test_choice_from_other_quiz_rejected(self):
        self.set_watched(self.v1, 300)
        q1 = self.n1.quiz.questions.first()
        foreign = self.n2.quiz.questions.first().choices.first()
        with self.assertRaises(InvalidAnswerError):
            services.submit_quiz(self.user, self.n1, {q1.pk: foreign.pk})

    def test_question_from_other_quiz_rejected(self):
        self.set_watched(self.v1, 300)
        foreign_q = self.n2.quiz.questions.first()
        with self.assertRaises(InvalidAnswerError):
            services.submit_quiz(
                self.user, self.n1, {foreign_q.pk: foreign_q.choices.first().pk}
            )


class CompletionTests(ProgressTestBase):
    def test_completing_twice_awards_xp_once(self):
        services.complete_node(self.user, self.n1)
        services.complete_node(self.user, self.n1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.xp, services.XP_PER_NODE_COMPLETED)

    def test_completing_does_not_relock_or_reset_next(self):
        services.complete_node(self.user, self.n1)
        services.complete_node(self.user, self.n2)
        services.complete_node(self.user, self.n1)  # replay
        self.assertEqual(self.status(self.n2), NodeProgress.Status.COMPLETED)

    def test_last_node_reports_roadmap_complete(self):
        self.assertFalse(services.complete_node(self.user, self.n1))
        self.assertFalse(services.complete_node(self.user, self.n2))
        self.assertTrue(services.complete_node(self.user, self.n3))
        self.assertEqual(
            services.roadmap_progress(self.user, self.roadmap),
            {"completed": 3, "total": 3, "percent": 100},
        )

    def test_locked_node_cannot_complete(self):
        with self.assertRaises(NodeLockedError):
            services.complete_node(self.user, self.n2)

    def test_no_quiz_node_completes_via_helper(self):
        roadmap = Roadmap.objects.create(title="NQ", slug="nq")
        node, video = make_node(roadmap, 1, with_quiz=False)
        services.enroll_user(self.user, roadmap)
        self.assertFalse(services.try_complete_node_without_quiz(self.user, node))
        self.set_watched(video, 300)
        self.assertTrue(services.try_complete_node_without_quiz(self.user, node))
        self.assertEqual(self.status(node), NodeProgress.Status.COMPLETED)

    def test_helper_does_not_bypass_real_quiz(self):
        self.set_watched(self.v1, 300)
        self.assertFalse(services.try_complete_node_without_quiz(self.user, self.n1))
        self.assertEqual(self.status(self.n1), NodeProgress.Status.UNLOCKED)

    def test_roadmap_progress_partial(self):
        services.complete_node(self.user, self.n1)
        self.assertEqual(
            services.roadmap_progress(self.user, self.roadmap),
            {"completed": 1, "total": 3, "percent": 33},
        )


class StreakTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("s", password="x")
        self.today = date(2026, 5, 10)

    def test_first_activity_starts_streak(self):
        services.update_streak(self.user, today=self.today)
        self.assertEqual(self.user.streak_days, 1)
        self.assertEqual(self.user.last_active_date, self.today)

    def test_same_day_no_change(self):
        services.update_streak(self.user, today=self.today)
        services.update_streak(self.user, today=self.today)
        self.assertEqual(self.user.streak_days, 1)

    def test_consecutive_day_increments(self):
        services.update_streak(self.user, today=self.today)
        services.update_streak(self.user, today=self.today + timedelta(days=1))
        self.assertEqual(self.user.streak_days, 2)

    def test_gap_resets_to_one(self):
        services.update_streak(self.user, today=self.today)
        services.update_streak(self.user, today=self.today + timedelta(days=1))
        services.update_streak(self.user, today=self.today + timedelta(days=4))
        self.assertEqual(self.user.streak_days, 1)
        self.assertEqual(self.user.last_active_date, self.today + timedelta(days=4))
