"""
progress/admin.py

NodeProgress, VideoProgress, RoadmapEnrollment are READ-ONLY in admin:
  - Superusers can view and delete.
  - Nobody can add or change them through the admin (they are created by app logic).
"""
from django.contrib import admin

from .models import NodeProgress, RoadmapEnrollment, VideoProgress


class ReadOnlyAdminMixin:
    """
    Disables add and change permissions; leaves view and delete for superusers.
    """
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff


@admin.register(NodeProgress)
class NodeProgressAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("user", "node", "status", "unlocked_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("user__username", "node__title", "node__roadmap__title")
    ordering = ("user", "node__roadmap", "node__order")


@admin.register(VideoProgress)
class VideoProgressAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("user", "video", "watched_seconds", "last_position", "last_heartbeat_at")
    search_fields = ("user__username", "video__title")
    ordering = ("user",)


@admin.register(RoadmapEnrollment)
class RoadmapEnrollmentAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("user", "roadmap", "enrolled_at")
    list_filter = ("roadmap",)
    search_fields = ("user__username", "roadmap__title")
