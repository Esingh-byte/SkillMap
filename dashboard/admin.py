"""
dashboard/admin.py

Badge is editable.
UserBadge is READ-ONLY (awarded by app logic).
"""
from django.contrib import admin

from .models import Badge, UserBadge


class ReadOnlyAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description")


@admin.register(UserBadge)
class UserBadgeAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("user", "badge", "awarded_at")
    list_filter = ("badge",)
    search_fields = ("user__username", "badge__name")
    date_hierarchy = "awarded_at"
