from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "xp",
        "streak_days",
        "last_active_date",
        "is_staff",
        "is_active",
    )
    list_filter = ("is_staff", "is_active", "is_superuser")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "RoadmapLearn Stats",
            {"fields": ("xp", "streak_days", "last_active_date")},
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "RoadmapLearn Stats",
            {"fields": ("xp", "streak_days", "last_active_date")},
        ),
    )
