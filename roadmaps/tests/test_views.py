from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from progress.models import NodeProgress, RoadmapEnrollment
from progress.services import enroll_user
from roadmaps.models import Category, Node, Roadmap


class RoadmapViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cat_a = Category.objects.create(name="Alpha", slug="alpha")
        cls.cat_b = Category.objects.create(name="Beta", slug="beta")
        cls.pub = Roadmap.objects.create(
            title="Pub", slug="pub", is_published=True, category=cls.cat_a
        )
        cls.pub_b = Roadmap.objects.create(
            title="PubB", slug="pub-b", is_published=True, category=cls.cat_b
        )
        cls.draft = Roadmap.objects.create(title="Draft", slug="draft")
        cls.n1 = Node.objects.create(roadmap=cls.pub, title="N1", slug="n1", order=1)
        cls.n2 = Node.objects.create(roadmap=cls.pub, title="N2", slug="n2", order=2)
        cls.user = User.objects.create_user("stu", password="pw12345!")

    def test_list_is_public_and_hides_drafts(self):
        resp = self.client.get(reverse("roadmaps:list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Pub")
        self.assertNotContains(resp, "Draft")

    def test_list_category_filter(self):
        resp = self.client.get(reverse("roadmaps:list"), {"category": "beta"})
        self.assertEqual([r.slug for r in resp.context["roadmaps"]], ["pub-b"])

    def test_detail_requires_login(self):
        url = reverse("roadmaps:detail", args=["pub"])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp["Location"])

    def test_detail_enrolls_and_shows_statuses(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("roadmaps:detail", args=["pub"]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            RoadmapEnrollment.objects.filter(user=self.user, roadmap=self.pub).exists()
        )
        self.assertEqual(
            [(r["node"].slug, r["status"]) for r in resp.context["nodes"]],
            [("n1", "UNLOCKED"), ("n2", "LOCKED")],
        )

    def test_detail_unpublished_404(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("roadmaps:detail", args=["draft"]))
        self.assertEqual(resp.status_code, 404)

    def test_node_requires_login(self):
        resp = self.client.get(reverse("roadmaps:node_detail", args=["pub", "n1"]))
        self.assertEqual(resp.status_code, 302)

    def test_node_not_enrolled_forbidden(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("roadmaps:node_detail", args=["pub", "n1"]))
        self.assertEqual(resp.status_code, 403)

    def test_locked_node_forbidden_unlocked_ok(self):
        enroll_user(self.user, self.pub)
        self.client.force_login(self.user)
        locked = self.client.get(reverse("roadmaps:node_detail", args=["pub", "n2"]))
        self.assertEqual(locked.status_code, 403)
        ok = self.client.get(reverse("roadmaps:node_detail", args=["pub", "n1"]))
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.context["status"], NodeProgress.Status.UNLOCKED)


class AccountViewTests(TestCase):
    def test_signup_creates_user_and_logs_in(self):
        resp = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "newbie",
                "email": "n@example.com",
                "password1": "Str0ngPass!word",
                "password2": "Str0ngPass!word",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(User.objects.filter(username="newbie").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_and_logout(self):
        User.objects.create_user("u", password="pw12345!")
        self.assertEqual(self.client.get(reverse("accounts:login")).status_code, 200)
        self.client.post(reverse("accounts:login"), {"username": "u", "password": "pw12345!"})
        self.assertIn("_auth_user_id", self.client.session)
        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
