from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    re_path(
        r"^static/(?P<path>.*)$",
        serve,
        {"document_root": settings.BASE_DIR / "static"},
    ),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("roadmaps/", include("roadmaps.urls", namespace="roadmaps")),
    path("progress/", include("progress.urls", namespace="progress")),
    path("quizzes/", include("quizzes.urls", namespace="quizzes")),
    path("notes/", include("notes.urls", namespace="notes")),
    path("", include("dashboard.urls", namespace="dashboard")),
]
