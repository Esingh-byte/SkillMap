from django.contrib import admin

from .models import Note


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("user", "node", "updated_at", "created_at")
    list_filter = ("node__roadmap",)
    search_fields = ("user__username", "node__title", "content")
    date_hierarchy = "updated_at"
