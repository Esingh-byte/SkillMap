import io
import json

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.template import Context, Engine
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from notes.models import Note
from progress.models import NodeProgress, RoadmapEnrollment, VideoProgress
from progress.services import XP_PER_NODE_COMPLETED, enroll_user
from quizzes.models import Choice, Question, Quiz
from roadmaps.models import Node, Roadmap, RoadmapBookmark, Video


class EndpointSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_a = User.objects.create_user("user_a", password="pw12345!")
        cls.user_b = User.objects.create_user("user_b", password="pw12345!")

        cls.roadmap = Roadmap.objects.create(
            title="Security Path", slug="sec-path", is_published=True
        )
        cls.n1 = Node.objects.create(
            roadmap=cls.roadmap, title="Node 1", slug="node-1", order=1
        )
        cls.n2 = Node.objects.create(
            roadmap=cls.roadmap, title="Node 2", slug="node-2", order=2
        )
        cls.v1 = Video.objects.create(
            node=cls.n1,
            youtube_id="sec_vid_001",
            title="Video 1",
            duration_seconds=100,
            order=1,
        )
        cls.v2 = Video.objects.create(
            node=cls.n2,
            youtube_id="sec_vid_002",
            title="Video 2",
            duration_seconds=100,
            order=1,
        )
        cls.quiz = Quiz.objects.create(node=cls.n1, title="Node 1 Quiz")
        cls.q1 = Question.objects.create(quiz=cls.quiz, text="2+2?", order=1)
        cls.c_right = Choice.objects.create(question=cls.q1, text="4", is_correct=True)
        cls.c_wrong = Choice.objects.create(question=cls.q1, text="5", is_correct=False)

        cls.heartbeat_url = reverse("progress:heartbeat")
        cls.quiz_url = reverse("quizzes:submit", args=[cls.n1.pk])
        cls.note_url = reverse("notes:save", args=[cls.n1.pk])
        cls.bookmark_url = reverse("roadmaps:bookmark", args=[cls.roadmap.slug])
        cls.enroll_url = reverse("roadmaps:detail", args=[cls.roadmap.slug])

    def test_anonymous_users_redirected_on_all_protected_endpoints(self):
        for url in (
            self.heartbeat_url,
            self.quiz_url,
            self.note_url,
            self.bookmark_url,
        ):
            with self.subTest(url=url):
                resp = self.client.post(url, data="{}", content_type="application/json")
                self.assertEqual(resp.status_code, 302)
                self.assertIn(reverse("accounts:login"), resp["Location"])

        resp_enroll = self.client.get(self.enroll_url)
        self.assertEqual(resp_enroll.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp_enroll["Location"])

    def test_get_not_allowed_on_post_only_endpoints(self):
        self.client.force_login(self.user_a)
        for url in (
            self.heartbeat_url,
            self.quiz_url,
            self.note_url,
            self.bookmark_url,
        ):
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 405)

    def test_csrf_enforced_on_all_post_endpoints(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user_a)

        for url in (
            self.heartbeat_url,
            self.quiz_url,
            self.note_url,
            self.bookmark_url,
        ):
            with self.subTest(url=url):
                resp = csrf_client.post(
                    url,
                    data=json.dumps({"content": "hi"}),
                    content_type="application/json",
                )
                self.assertEqual(resp.status_code, 403)

    def test_user_a_cannot_modify_user_b_progress_or_notes(self):
        enroll_user(self.user_b, self.roadmap)
        VideoProgress.objects.create(
            user=self.user_b, video=self.v1, watched_seconds=40
        )
        Note.objects.create(user=self.user_b, node=self.n1, content="User B private note")

        enroll_user(self.user_a, self.roadmap)
        self.client.force_login(self.user_a)

        # User A saves a note and sends a heartbeat (even passing a spoofed user_id field)
        self.client.post(
            self.note_url,
            data=json.dumps({"user_id": self.user_b.pk, "content": "User A note"}),
            content_type="application/json",
        )
        self.client.post(
            self.heartbeat_url,
            data=json.dumps(
                {
                    "user_id": self.user_b.pk,
                    "video_id": self.v1.pk,
                    "current_time": 10.0,
                    "playback_rate": 1.0,
                }
            ),
            content_type="application/json",
        )
        self.client.post(self.bookmark_url)

        # User B's note, watch progress, and bookmarks are untouched
        self.assertEqual(
            Note.objects.get(user=self.user_b, node=self.n1).content,
            "User B private note",
        )
        self.assertEqual(
            VideoProgress.objects.get(user=self.user_b, video=self.v1).watched_seconds,
            40,
        )
        self.assertFalse(
            RoadmapBookmark.objects.filter(
                user=self.user_b, roadmap=self.roadmap
            ).exists()
        )

    def test_malformed_json_and_bad_numeric_inputs_return_400_never_500(self):
        enroll_user(self.user_a, self.roadmap)
        VideoProgress.objects.create(
            user=self.user_a, video=self.v1, watched_seconds=100
        )
        self.client.force_login(self.user_a)

        bad_heartbeat_bodies = [
            b"{malformed json",
            b"[]",
            b"123",
            b"{}",
            json.dumps({"video_id": self.v1.pk}).encode(),
            json.dumps({"video_id": "abc", "current_time": 10}).encode(),
            json.dumps({"video_id": self.v1.pk, "current_time": "not-a-num"}).encode(),
            json.dumps({"video_id": self.v1.pk, "current_time": -5}).encode(),
            json.dumps({"video_id": True, "current_time": 10}).encode(),
            json.dumps({"video_id": self.v1.pk, "current_time": False}).encode(),
            json.dumps({"video_id": self.v1.pk, "current_time": "Infinity"}).encode(),
            json.dumps({"video_id": self.v1.pk, "current_time": "-Infinity"}).encode(),
            json.dumps({"video_id": self.v1.pk, "current_time": "NaN"}).encode(),
            json.dumps({"video_id": self.v1.pk, "current_time": 10, "playback_rate": "Infinity"}).encode(),
            json.dumps({"video_id": 10**30, "current_time": 10}).encode(),
        ]
        for body in bad_heartbeat_bodies:
            with self.subTest(endpoint="heartbeat", body=body):
                resp = self.client.post(
                    self.heartbeat_url, data=body, content_type="application/json"
                )
                self.assertEqual(resp.status_code, 400)

        bad_quiz_bodies = [
            b"{malformed",
            b"[]",
            b"{}",
            json.dumps({"answers": "not-a-dict"}).encode(),
            json.dumps({"answers": {str(self.q1.pk): "not-an-int"}}).encode(),
            json.dumps({"answers": {str(self.q1.pk): True}}).encode(),
        ]
        for body in bad_quiz_bodies:
            with self.subTest(endpoint="quiz", body=body):
                resp = self.client.post(
                    self.quiz_url, data=body, content_type="application/json"
                )
                self.assertEqual(resp.status_code, 400)

        bad_note_bodies = [
            b"{malformed",
            b"[]",
            b"{}",
            json.dumps({"content": 12345}).encode(),
            json.dumps({"content": None}).encode(),
        ]
        for body in bad_note_bodies:
            with self.subTest(endpoint="note", body=body):
                resp = self.client.post(
                    self.note_url, data=body, content_type="application/json"
                )
                self.assertEqual(resp.status_code, 400)

    def test_heartbeat_on_locked_node_rejected_403(self):
        enroll_user(self.user_a, self.roadmap)
        self.client.force_login(self.user_a)
        resp = self.client.post(
            self.heartbeat_url,
            data=json.dumps({"video_id": self.v2.pk, "current_time": 5.0}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_quiz_submit_before_video_check_rejected_403(self):
        enroll_user(self.user_a, self.roadmap)
        self.client.force_login(self.user_a)
        resp = self.client.post(
            self.quiz_url,
            data=json.dumps({"answers": {str(self.q1.pk): self.c_right.pk}}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)


class ErrorPagesTests(TestCase):
    def test_missing_secret_key_when_debug_false_raises_improperly_configured(self):
        import importlib
        import os
        from unittest.mock import patch
        import roadmaplearn.settings as app_settings

        with patch.dict(os.environ, {"DEBUG": "False", "SECRET_KEY": ""}, clear=False):
            with self.assertRaises(ImproperlyConfigured):
                importlib.reload(app_settings)
        # Restore dev settings reload
        importlib.reload(app_settings)

    def test_404_template_renders(self):
        resp = self.client.get("/non-existent-top-level-route-404/")
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, "ERROR 404", status_code=404)

    def test_500_template_renders_without_context_processors(self):
        # Render 500.html using a bare Engine with zero context processors
        from django.conf import settings

        bare_engine = Engine(dirs=[str(settings.BASE_DIR / "templates")], context_processors=[])
        template = bare_engine.get_template("500.html")
        rendered = template.render(Context({}))
        self.assertIn("ERROR 500", rendered)
        self.assertIn("Something went wrong on our end.", rendered)


class DemoFastForwardCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("demouser", password="pw12345!")
        self.roadmap = Roadmap.objects.create(
            title="Demo FastForward Path", slug="ff-path", is_published=True
        )
        self.n1 = Node.objects.create(
            roadmap=self.roadmap, title="Step 1", slug="step-1", order=1
        )
        self.n2 = Node.objects.create(
            roadmap=self.roadmap, title="Step 2", slug="step-2", order=2
        )
        self.n3 = Node.objects.create(
            roadmap=self.roadmap, title="Step 3", slug="step-3", order=3
        )
        self.n4 = Node.objects.create(
            roadmap=self.roadmap, title="Step 4", slug="step-4", order=4
        )

    @override_settings(DEBUG=False)
    def test_refuses_to_run_when_debug_is_false(self):
        with self.assertRaisesMessage(
            CommandError, "Refusing to run demo_fastforward when settings.DEBUG is False."
        ):
            call_command("demo_fastforward", "demouser", "ff-path", 3)

    @override_settings(DEBUG=True)
    def test_enrolls_completes_earlier_nodes_and_leaves_target_unlocked(self):
        out = io.StringIO()
        call_command("demo_fastforward", "demouser", "ff-path", 3, stdout=out)

        self.assertTrue(
            RoadmapEnrollment.objects.filter(
                user=self.user, roadmap=self.roadmap
            ).exists()
        )
        statuses = dict(
            NodeProgress.objects.filter(
                user=self.user, node__roadmap=self.roadmap
            ).values_list("node__order", "status")
        )
        self.assertEqual(
            statuses,
            {
                1: NodeProgress.Status.COMPLETED,
                2: NodeProgress.Status.COMPLETED,
                3: NodeProgress.Status.UNLOCKED,
                4: NodeProgress.Status.LOCKED,
            },
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.xp, 2 * XP_PER_NODE_COMPLETED)
        self.assertEqual(self.user.streak_days, 1)

    @override_settings(DEBUG=True)
    def test_errors_on_unknown_user_roadmap_or_order(self):
        with self.assertRaises(CommandError):
            call_command("demo_fastforward", "nobody", "ff-path", 2)
        with self.assertRaises(CommandError):
            call_command("demo_fastforward", "demouser", "no-such-roadmap", 2)
        with self.assertRaises(CommandError):
            call_command("demo_fastforward", "demouser", "ff-path", 99)
