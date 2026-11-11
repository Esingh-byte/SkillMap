"""
roadmaps/admin.py

Hierarchy in the admin:
  Roadmap → NodeInline (ordered by order)

  Node (own page, via NodeAdmin):
    ├── VideoInline          (nested_admin.NestedTabularInline)
    └── QuizInline           (nested_admin.NestedStackedInline)
         └── QuestionInline  (nested_admin.NestedTabularInline)
              └── ChoiceInline (nested_admin.NestedTabularInline)
"""
from django import forms
from django.contrib import admin
from django.db.models import Count, Sum
from django.utils.html import format_html

import nested_admin

from quizzes.models import Choice, Question, Quiz

from .models import Category, Node, Roadmap, RoadmapBookmark, Video


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_duration(seconds):
    """Return seconds as mm:ss string."""
    if not seconds:
        return "—"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# Choice formset validation: ≥2 choices, exactly 1 correct
# ---------------------------------------------------------------------------

class ChoiceFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self._non_form_errors()):
            return
        # Count non-deleted, filled forms
        filled = [
            f for f in self.forms
            if f.cleaned_data and not f.cleaned_data.get("DELETE", False)
        ]
        if len(filled) < 2:
            raise forms.ValidationError(
                "Each question must have at least 2 choices."
            )
        correct = sum(1 for f in filled if f.cleaned_data.get("is_correct", False))
        if correct != 1:
            raise forms.ValidationError(
                f"Each question must have exactly 1 correct choice (found {correct})."
            )


# ---------------------------------------------------------------------------
# Node order uniqueness validation
# ---------------------------------------------------------------------------

class NodeFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        orders = [
            f.cleaned_data.get("order")
            for f in self.forms
            if f.cleaned_data and not f.cleaned_data.get("DELETE", False)
        ]
        seen = set()
        for o in orders:
            if o is not None:
                if o in seen:
                    raise forms.ValidationError(
                        f"Node order {o} appears more than once in this roadmap. "
                        "Each node must have a unique order number."
                    )
                seen.add(o)


# ---------------------------------------------------------------------------
# Nested inlines for Node admin page
# ---------------------------------------------------------------------------

class ChoiceInline(nested_admin.NestedTabularInline):
    model = Choice
    formset = ChoiceFormSet
    extra = 4
    fields = ("text", "is_correct")
    classes = ("collapse",)


class QuestionInline(nested_admin.NestedTabularInline):
    model = Question
    extra = 1
    fields = ("order", "text")
    ordering = ("order",)
    inlines = [ChoiceInline]
    classes = ("collapse",)


class QuizInline(nested_admin.NestedStackedInline):
    model = Quiz
    extra = 0
    max_num = 1
    fields = ("title",)
    inlines = [QuestionInline]
    classes = ("collapse",)


class VideoNestedInline(nested_admin.NestedTabularInline):
    model = Video
    extra = 1
    fields = ("order", "youtube_id", "title", "channel_name", "duration_seconds", "is_embeddable")
    ordering = ("order",)


# ---------------------------------------------------------------------------
# NodeInline for Roadmap admin page (plain TabularInline – no nesting needed)
# ---------------------------------------------------------------------------

class NodeInline(nested_admin.NestedTabularInline):
    model = Node
    formset = NodeFormSet
    extra = 0
    fields = ("order", "title", "slug", "quiz_pass_mark")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("order",)
    show_change_link = True


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


# ---------------------------------------------------------------------------
# Roadmap
# ---------------------------------------------------------------------------

@admin.register(Roadmap)
class RoadmapAdmin(nested_admin.NestedModelAdmin):
    list_display = (
        "title",
        "category",
        "is_published",
        "node_count",
        "total_video_minutes",
        "updated_at",
    )
    list_filter = ("category", "is_published")
    search_fields = ("title", "description", "source_attribution")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [NodeInline]
    date_hierarchy = "created_at"
    actions = ["publish_selected", "unpublish_selected"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _node_count=Count("nodes", distinct=True),
            _total_duration=Sum("nodes__videos__duration_seconds"),
        )

    @admin.display(description="Nodes", ordering="_node_count")
    def node_count(self, obj):
        return obj._node_count

    @admin.display(description="Video time", ordering="_total_duration")
    def total_video_minutes(self, obj):
        total = obj._total_duration or 0
        m, s = divmod(total, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}h {m}m"
        return f"{m}m {s}s"

    @admin.action(description="Publish selected roadmaps")
    def publish_selected(self, request, queryset):
        updated = queryset.update(is_published=True)
        self.message_user(request, f"{updated} roadmap(s) published.")

    @admin.action(description="Unpublish selected roadmaps")
    def unpublish_selected(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f"{updated} roadmap(s) unpublished.")


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

@admin.register(Node)
class NodeAdmin(nested_admin.NestedModelAdmin):
    list_display = ("roadmap", "order", "title", "video_count", "has_quiz", "quiz_pass_mark")
    list_filter = ("roadmap",)
    search_fields = ("title", "description")
    list_editable = ("order",)
    ordering = ("roadmap", "order")
    inlines = [VideoNestedInline, QuizInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _video_count=Count("videos", distinct=True),
        ).select_related("roadmap")

    @admin.display(description="Videos", ordering="_video_count")
    def video_count(self, obj):
        return obj._video_count

    @admin.display(description="Has quiz?", boolean=True)
    def has_quiz(self, obj):
        return hasattr(obj, "quiz")


# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------

@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "youtube_id",
        "node",
        "order",
        "duration_display",
        "embeddable_icon",
    )
    list_filter = ("is_embeddable", "node__roadmap")
    search_fields = ("title", "youtube_id", "channel_name")

    @admin.display(description="Duration", ordering="duration_seconds")
    def duration_display(self, obj):
        return _fmt_duration(obj.duration_seconds)

    @admin.display(description="Embeddable?", boolean=False, ordering="is_embeddable")
    def embeddable_icon(self, obj):
        if obj.is_embeddable:
            return format_html('<span style="color:green;font-weight:bold;">✔</span>')
        return format_html('<span style="color:red;font-weight:bold;">✘ NOT EMBEDDABLE</span>')


# ---------------------------------------------------------------------------
# RoadmapBookmark
# ---------------------------------------------------------------------------

@admin.register(RoadmapBookmark)
class RoadmapBookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "roadmap", "created_at")
    list_filter = ("roadmap",)
    search_fields = ("user__username", "roadmap__title")
