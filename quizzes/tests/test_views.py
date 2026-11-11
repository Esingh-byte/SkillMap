import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from notes.models import Note
from progress.models import NodeProgress, VideoProgress
from progress.services import XP_PER_NODE_COMPLETED, enroll_user
from quizzes.models import Choice, Question, Quiz
from roadmaps.models import Node, Roadmap, Video


class QuizAndNoteViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.roadmap = Roadmap.objects.create(title="R", slug="r", is_published=True)
        cls.n1 = Node.objects.create(
            roadmap=cls.roadmap, title="N1", slug="n1", order=1, quiz_pass_mark=100
        )
        cls.n2 = Node.objects.create(roadmap=cls.roadmap, title="N2", slug="n2", order=2)
        cls.video = Video.objects.create(
            node=cls.n1, youtube_id="aaaaaaaaaaa", title="V", duration_seconds=100, order=1
        )
        quiz = Quiz.objects.create(node=cls.n1)
        cls.q = Question.objects.create(quiz=quiz, text="2+2?", order=1)
        cls.right = Choice.objects.create(question=cls.q, text="4", is_correct=True)
        cls.wrong = Choice.objects.create(question=cls.q, text="5")
        cls.user = User.objects.create_user("stu", password="pw12345!")
        cls.quiz_url = reverse("quizzes:submit", args=[cls.n1.pk])

    def post(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    def watch_enough(self):
        VideoProgress.objects.update_or_create(
            user=self.user, video=self.video, defaults={"watched_seconds": 100}
        )

    # --- quiz -----------------------------------------------------------
    def test_quiz_requires_login(self):
        resp = self.post(self.quiz_url, {"answers": {}})
        self.assertEqual(resp.status_code, 302)

    def test_quiz_video_check_not_passed_403(self):
        enroll_user(self.user, self.roadmap)
        self.client.force_login(self.user)
        resp = self.post(self.quiz_url, {"answers": {str(self.q.pk): self.right.pk}})
        self.assertEqual(resp.status_code, 403)

    def test_quiz_locked_node_403(self):
        enroll_user(self.user, self.roadmap)
        self.client.force_login(self.user)
        url = reverse("quizzes:submit", args=[self.n2.pk])
        self.assertEqual(self.post(url, {"answers": {}}).status_code, 403)

    def test_quiz_invalid_answers_400(self):
        enroll_user(self.user, self.roadmap)
        self.watch_enough()
        self.client.force_login(self.user)
        self.assertEqual(self.post(self.quiz_url, {"answers": [1]}).status_code, 400)
        self.assertEqual(self.post(self.quiz_url, {"answers": {"99999": 1}}).status_code, 400)
        self.assertEqual(
            self.post(self.quiz_url, {"answers": {str(self.q.pk): 99999}}).status_code, 400
        )

    def test_quiz_fail_does_not_unlock(self):
        enroll_user(self.user, self.roadmap)
        self.watch_enough()
        self.client.force_login(self.user)
        data = self.post(self.quiz_url, {"answers": {str(self.q.pk): self.wrong.pk}}).json()
        self.assertFalse(data["passed"])
        self.assertFalse(data["node_completed"])
        self.assertEqual(data["xp_awarded"], 0)
        self.assertEqual(
            NodeProgress.objects.get(user=self.user, node=self.n2).status,
            NodeProgress.Status.LOCKED,
        )

    def test_quiz_pass_unlocks_next_node(self):
        enroll_user(self.user, self.roadmap)
        self.watch_enough()
        self.client.force_login(self.user)
        data = self.post(self.quiz_url, {"answers": {str(self.q.pk): self.right.pk}}).json()
        self.assertTrue(data["passed"])
        self.assertEqual(data["score_percent"], 100.0)
        self.assertTrue(data["node_completed"])
        self.assertEqual(data["xp_awarded"], XP_PER_NODE_COMPLETED)
        self.assertEqual(
            NodeProgress.objects.get(user=self.user, node=self.n2).status,
            NodeProgress.Status.UNLOCKED,
        )
        # Resubmitting does not award XP twice.
        again = self.post(self.quiz_url, {"answers": {str(self.q.pk): self.right.pk}}).json()
        self.assertEqual(again["xp_awarded"], 0)

    # --- notes ----------------------------------------------------------
    def test_note_requires_login(self):
        url = reverse("notes:save", args=[self.n1.pk])
        resp = self.post(url, {"content": "x"})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Note.objects.exists())

    def test_note_save_json_upserts(self):
        self.client.force_login(self.user)
        url = reverse("notes:save", args=[self.n1.pk])
        first = self.post(url, {"content": "one"}).json()
        self.assertEqual(first["status"], "saved")
        self.assertTrue(first["updated_at"])
        self.post(url, {"content": "two"})
        self.assertEqual(Note.objects.filter(user=self.user, node=self.n1).count(), 1)
        self.assertEqual(Note.objects.get(user=self.user, node=self.n1).content, "two")

    def test_note_save_form_data(self):
        self.client.force_login(self.user)
        url = reverse("notes:save", args=[self.n1.pk])
        resp = self.client.post(url, {"content": "form"})
        self.assertEqual(resp.json()["status"], "saved")
        self.assertEqual(Note.objects.get().content, "form")

    def test_note_bad_content_400(self):
        self.client.force_login(self.user)
        url = reverse("notes:save", args=[self.n1.pk])
        self.assertEqual(self.post(url, {"content": 5}).status_code, 400)
        self.assertEqual(self.post(url, {}).status_code, 400)

    def test_note_unknown_node_404(self):
        self.client.force_login(self.user)
        self.assertEqual(self.post(reverse("notes:save", args=[99999]), {"content": "x"}).status_code, 404)
