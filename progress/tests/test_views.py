import json
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from progress.models import NodeProgress, VideoProgress
from progress.services import enroll_user
from quizzes.models import Choice, Question, Quiz
from roadmaps.models import Node, Roadmap, Video


class HeartbeatViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.roadmap = Roadmap.objects.create(title="R", slug="r", is_published=True)
        cls.n1 = Node.objects.create(roadmap=cls.roadmap, title="N1", slug="n1", order=1)
        cls.n2 = Node.objects.create(roadmap=cls.roadmap, title="N2", slug="n2", order=2)
        cls.v1 = Video.objects.create(
            node=cls.n1, youtube_id="aaaaaaaaaaa", title="V1", duration_seconds=100, order=1
        )
        cls.v2 = Video.objects.create(
            node=cls.n2, youtube_id="bbbbbbbbbbb", title="V2", duration_seconds=100, order=1
        )
        cls.user = User.objects.create_user("stu", password="pw12345!")
        cls.url = reverse("progress:heartbeat")

    def post(self, payload):
        return self.client.post(
            self.url, data=json.dumps(payload), content_type="application/json"
        )

    def payload(self, video, t=0.0):
        return {"video_id": video.pk, "current_time": t, "playback_rate": 1.0}

    def test_requires_login(self):
        resp = self.post(self.payload(self.v1))
        self.assertEqual(resp.status_code, 302)

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_not_enrolled_403(self):
        self.client.force_login(self.user)
        resp = self.post(self.payload(self.v1))
        self.assertEqual(resp.status_code, 403)
        self.assertIn("error", resp.json())

    def test_locked_node_403(self):
        enroll_user(self.user, self.roadmap)
        self.client.force_login(self.user)
        resp = self.post(self.payload(self.v2))
        self.assertEqual(resp.status_code, 403)

    def test_non_embeddable_400(self):
        enroll_user(self.user, self.roadmap)
        Video.objects.filter(pk=self.v1.pk).update(is_embeddable=False)
        self.client.force_login(self.user)
        resp = self.post(self.payload(self.v1))
        self.assertEqual(resp.status_code, 400)

    def test_bad_payload_400(self):
        self.client.force_login(self.user)
        self.assertEqual(self.post({"video_id": "x"}).status_code, 400)
        resp = self.client.post(self.url, data="nope", content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_unknown_video_404(self):
        self.client.force_login(self.user)
        self.assertEqual(self.post({"video_id": 99999, "current_time": 0}).status_code, 404)

    def test_progression_credits_watch_time(self):
        enroll_user(self.user, self.roadmap)
        self.client.force_login(self.user)
        first = self.post(self.payload(self.v1, 0)).json()
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["watched_seconds"], 0)
        self.assertEqual(first["duration_seconds"], 100)
        self.assertFalse(first["video_passed"])
        VideoProgress.objects.filter(user=self.user, video=self.v1).update(
            last_heartbeat_at=timezone.now() - timedelta(seconds=10)
        )
        second = self.post(self.payload(self.v1, 5)).json()
        self.assertEqual(second["watched_seconds"], 5)

    def test_seek_forward_gives_little_credit(self):
        enroll_user(self.user, self.roadmap)
        self.client.force_login(self.user)
        self.post(self.payload(self.v1, 0))
        resp = self.post(self.payload(self.v1, 90)).json()
        self.assertLessEqual(resp["watched_seconds"], 3)
        self.assertFalse(resp["video_passed"])

    def test_no_quiz_node_completes_and_unlocks_next(self):
        enroll_user(self.user, self.roadmap)
        VideoProgress.objects.create(
            user=self.user, video=self.v1, watched_seconds=95,
            last_position=95, last_heartbeat_at=timezone.now(),
        )
        self.client.force_login(self.user)
        resp = self.post(self.payload(self.v1, 95)).json()
        self.assertTrue(resp["video_passed"])
        self.assertTrue(resp["node_completed"])
        self.assertEqual(
            NodeProgress.objects.get(user=self.user, node=self.n2).status,
            NodeProgress.Status.UNLOCKED,
        )

    def test_quiz_node_not_completed_by_video_alone(self):
        quiz = Quiz.objects.create(node=self.n1)
        q = Question.objects.create(quiz=quiz, text="?", order=1)
        Choice.objects.create(question=q, text="a", is_correct=True)
        Choice.objects.create(question=q, text="b")
        enroll_user(self.user, self.roadmap)
        VideoProgress.objects.create(
            user=self.user, video=self.v1, watched_seconds=95,
            last_position=95, last_heartbeat_at=timezone.now(),
        )
        self.client.force_login(self.user)
        resp = self.post(self.payload(self.v1, 95)).json()
        self.assertTrue(resp["video_passed"])
        self.assertFalse(resp["node_completed"])
