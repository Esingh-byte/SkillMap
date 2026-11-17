import io
from datetime import date, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from dashboard.models import Badge, UserBadge
from dashboard.services import (
    BADGE_DEFINITIONS,
    award_badges,
    effective_streak,
)
from notes.models import Note
from progress.models import NodeProgress, VideoProgress
from progress.services import complete_node, enroll_user, submit_quiz
from quizzes.models import Choice, Question, Quiz, QuizAttempt
from roadmaps.models import Node, Roadmap, Video


class SeedBadgesCommandTests(TestCase):
    def test_seed_badges_is_idempotent(self):
        out1 = io.StringIO()
        call_command("seed_badges", stdout=out1)
        self.assertEqual(Badge.objects.count(), 6)
        self.assertIn("created=6, existing=0", out1.getvalue())

        out2 = io.StringIO()
        call_command("seed_badges", stdout=out2)
        self.assertEqual(Badge.objects.count(), 6)
        self.assertIn("created=0, existing=6", out2.getvalue())

        expected_slugs = {b["slug"] for b in BADGE_DEFINITIONS}
        self.assertEqual(
            set(Badge.objects.values_list("slug", flat=True)),
            expected_slugs,
        )


class EffectiveStreakTests(TestCase):
    def setUp(self):
        self.today = date(2026, 11, 17)
        self.user = User.objects.create_user("streaker", password="pw12345!")

    def test_fresh_today_and_yesterday_return_streak_days(self):
        self.user.streak_days = 5
        self.user.last_active_date = self.today
        self.user.save()
        self.assertEqual(effective_streak(self.user, today=self.today), 5)

        self.user.last_active_date = self.today - timedelta(days=1)
        self.user.save()
        self.assertEqual(effective_streak(self.user, today=self.today), 5)

    def test_stale_streak_returns_zero_and_never_writes_to_db(self):
        self.user.streak_days = 9
        self.user.last_active_date = self.today - timedelta(days=2)
        self.user.save()

        self.assertEqual(effective_streak(self.user, today=self.today), 0)
        # Verify database row is untouched
        self.user.refresh_from_db()
        self.assertEqual(self.user.streak_days, 9)
        self.assertEqual(self.user.last_active_date, self.today - timedelta(days=2))

    def test_none_last_active_date_returns_zero(self):
        self.user.streak_days = 4
        self.user.last_active_date = None
        self.user.save()
        self.assertEqual(effective_streak(self.user, today=self.today), 0)


class BadgeEngineRulesTests(TestCase):
    def setUp(self):
        call_command("seed_badges", stdout=io.StringIO())
        self.today = date(2026, 11, 17)
        self.user = User.objects.create_user("learner", password="pw12345!")
        self.roadmap = Roadmap.objects.create(
            title="Python Path", slug="python-path", is_published=True
        )
        self.nodes = [
            Node.objects.create(
                roadmap=self.roadmap,
                title=f"Topic {i}",
                slug=f"topic-{i}",
                order=i,
            )
            for i in range(1, 6)
        ]

    def test_new_user_earns_no_badges(self):
        awarded = award_badges(self.user, today=self.today)
        self.assertEqual(awarded, [])
        self.assertEqual(UserBadge.objects.filter(user=self.user).count(), 0)

    def test_first_step_rule_and_idempotency(self):
        # LOCKED or UNLOCKED does not earn first_step
        NodeProgress.objects.create(
            user=self.user,
            node=self.nodes[0],
            status=NodeProgress.Status.UNLOCKED,
        )
        self.assertEqual(award_badges(self.user, today=self.today), [])

        # Completing 1 topic earns first_step (5 nodes in roadmap so roadmap_finisher is not earned)
        NodeProgress.objects.filter(user=self.user, node=self.nodes[0]).update(
            status=NodeProgress.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        awarded = award_badges(self.user, today=self.today)
        self.assertEqual([b.slug for b in awarded], ["first_step"])

        # Calling a second time is idempotent and returns empty list
        self.assertEqual(award_badges(self.user, today=self.today), [])
        self.assertEqual(UserBadge.objects.filter(user=self.user).count(), 1)

    def test_on_a_roll_and_week_warrior_streak_rules(self):
        self.user.last_active_date = self.today
        self.user.streak_days = 2
        self.user.save()
        self.assertEqual(award_badges(self.user, today=self.today), [])

        self.user.streak_days = 3
        self.user.save()
        awarded_3 = award_badges(self.user, today=self.today)
        self.assertEqual([b.slug for b in awarded_3], ["on_a_roll"])

        self.user.streak_days = 6
        self.user.save()
        self.assertEqual(award_badges(self.user, today=self.today), [])

        self.user.streak_days = 7
        self.user.save()
        awarded_7 = award_badges(self.user, today=self.today)
        self.assertEqual([b.slug for b in awarded_7], ["week_warrior"])

    def test_stale_streak_does_not_earn_streak_badges(self):
        self.user.streak_days = 7
        self.user.last_active_date = self.today - timedelta(days=3)
        self.user.save()
        self.assertEqual(award_badges(self.user, today=self.today), [])

    def test_quiz_ace_rule(self):
        quiz = Quiz.objects.create(node=self.nodes[0], title="Q1")
        QuizAttempt.objects.create(
            user=self.user, quiz=quiz, score_percent=80, passed=True
        )
        self.assertEqual(award_badges(self.user, today=self.today), [])

        QuizAttempt.objects.create(
            user=self.user, quiz=quiz, score_percent=100, passed=True
        )
        awarded = award_badges(self.user, today=self.today)
        self.assertEqual([b.slug for b in awarded], ["quiz_ace"])

    def test_roadmap_finisher_rule(self):
        short_rm = Roadmap.objects.create(
            title="Short Path", slug="short-path", is_published=True
        )
        n1 = Node.objects.create(roadmap=short_rm, title="S1", slug="s1", order=1)
        n2 = Node.objects.create(roadmap=short_rm, title="S2", slug="s2", order=2)

        NodeProgress.objects.create(
            user=self.user,
            node=n1,
            status=NodeProgress.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        awarded_partial = [b.slug for b in award_badges(self.user, today=self.today)]
        self.assertIn("first_step", awarded_partial)
        self.assertNotIn("roadmap_finisher", awarded_partial)

        NodeProgress.objects.create(
            user=self.user,
            node=n2,
            status=NodeProgress.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        awarded_done = [b.slug for b in award_badges(self.user, today=self.today)]
        self.assertEqual(awarded_done, ["roadmap_finisher"])

    def test_note_taker_rule(self):
        for i in range(4):
            Note.objects.create(
                user=self.user, node=self.nodes[i], content=f"Note {i}"
            )
        self.assertEqual(award_badges(self.user, today=self.today), [])

        # Blank note on 5th topic does not count
        note5 = Note.objects.create(
            user=self.user, node=self.nodes[4], content=""
        )
        self.assertEqual(award_badges(self.user, today=self.today), [])

        # Non-empty note on 5th topic awards note_taker
        note5.content = "Fifth topic note"
        note5.save()
        awarded = award_badges(self.user, today=self.today)
        self.assertEqual([b.slug for b in awarded], ["note_taker"])

    def test_complete_node_and_submit_quiz_hooks_award_badges_automatically(self):
        short_rm = Roadmap.objects.create(
            title="Single Node Path", slug="single-node", is_published=True
        )
        node = Node.objects.create(
            roadmap=short_rm, title="Only Node", slug="only-node", order=1
        )
        video = Video.objects.create(
            node=node, youtube_id="vid12345678", title="V", duration_seconds=100, order=1
        )
        quiz = Quiz.objects.create(node=node)
        q = Question.objects.create(quiz=quiz, text="1+1?", order=1)
        right = Choice.objects.create(question=q, text="2", is_correct=True)
        Choice.objects.create(question=q, text="3", is_correct=False)

        enroll_user(self.user, short_rm)
        VideoProgress.objects.create(
            user=self.user, video=video, watched_seconds=100
        )

        attempt = submit_quiz(self.user, node, {q.pk: right.pk})
        self.assertTrue(attempt.passed)

        earned_slugs = set(
            UserBadge.objects.filter(user=self.user).values_list(
                "badge__slug", flat=True
            )
        )
        self.assertEqual(
            earned_slugs,
            {"first_step", "quiz_ace", "roadmap_finisher"},
        )


class DashboardViewTests(TestCase):
    def setUp(self):
        call_command("seed_badges", stdout=io.StringIO())
        self.user = User.objects.create_user(
            "dashuser", password="pw12345!", xp=150, streak_days=4
        )
        self.user.last_active_date = timezone.localdate()
        self.user.save()

        self.roadmap = Roadmap.objects.create(
            title="Backend Engineering", slug="backend-eng", is_published=True
        )
        self.n1 = Node.objects.create(
            roadmap=self.roadmap, title="HTTP Fundamentals", slug="http-fundamentals", order=1
        )
        self.n2 = Node.objects.create(
            roadmap=self.roadmap, title="Relational Databases", slug="relational-dbs", order=2
        )
        self.n3 = Node.objects.create(
            roadmap=self.roadmap, title="Caching Strategies", slug="caching-strategies", order=3
        )
        self.url = reverse("dashboard:home")

    def test_anonymous_redirects_to_login(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp["Location"])

    def test_empty_state_for_new_user_links_to_roadmap_list(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["enrolled_roadmaps"], [])
        self.assertContains(resp, "You haven't started a roadmap yet.")
        self.assertContains(resp, reverse("roadmaps:list"))

    def test_enrolled_roadmap_shows_progress_and_next_unlocked_node_link(self):
        enroll_user(self.user, self.roadmap)
        complete_node(self.user, self.n1)

        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

        enrolled = resp.context["enrolled_roadmaps"]
        self.assertEqual(len(enrolled), 1)
        self.assertEqual(enrolled[0]["next_node"], self.n2)
        self.assertEqual(enrolled[0]["progress"]["completed"], 1)
        self.assertEqual(enrolled[0]["progress"]["total"], 3)

        expected_next_url = reverse(
            "roadmaps:node_detail", args=[self.roadmap.slug, self.n2.slug]
        )
        self.assertContains(resp, expected_next_url)
        self.assertContains(resp, "First Step")
        self.assertContains(resp, "How to earn:")
