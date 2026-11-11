from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse


class AdminSmokeTests(TestCase):
    """Hit every registered admin page so list-display crashes fail in tests."""

    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="test-pass-123",
        )
        call_command("seed_demo")
        self.assertTrue(
            self.client.login(username="admin", password="test-pass-123")
        )
        self.admin_request = RequestFactory().get("/admin/")
        self.admin_request.user = self.superuser

    def _assert_ok(self, model, url):
        response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            200,
            f"{model._meta.label} GET {url} returned HTTP {response.status_code}",
        )

    def test_changelist_pages_return_200(self):
        for model in admin.site._registry:
            url = reverse(
                f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist"
            )
            with self.subTest(model=model._meta.label, url=url):
                self._assert_ok(model, url)

    def test_change_pages_return_200(self):
        for model in admin.site._registry:
            obj = model.objects.first()
            if obj is None:
                continue
            url = reverse(
                f"admin:{model._meta.app_label}_{model._meta.model_name}_change",
                args=[obj.pk],
            )
            with self.subTest(model=model._meta.label, url=url):
                self._assert_ok(model, url)

    def test_add_pages_return_200(self):
        for model, model_admin in admin.site._registry.items():
            if not model_admin.has_add_permission(self.admin_request):
                continue
            url = reverse(
                f"admin:{model._meta.app_label}_{model._meta.model_name}_add"
            )
            with self.subTest(model=model._meta.label, url=url):
                self._assert_ok(model, url)
