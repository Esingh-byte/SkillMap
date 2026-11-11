from django.db import models
from django.conf import settings


class Category(models.Model):
    """High-level grouping for roadmaps (e.g. 'Programming', 'Data Science')."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
        ]

    def __str__(self) -> str:
        return self.name


class Roadmap(models.Model):
    """A learning roadmap (e.g. 'Python Developer', 'Machine Learning')."""

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="roadmaps",
    )
    thumbnail = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path or URL to the thumbnail image. Switch to ImageField once Pillow is installed.",
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Attribution
    source_attribution = models.CharField(
        max_length=255,
        blank=True,
        help_text="e.g. 'roadmap.sh – Python Roadmap'",
    )

    class Meta:
        verbose_name = "Roadmap"
        verbose_name_plural = "Roadmaps"
        ordering = ["title"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_published"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self) -> str:
        return self.title


class RoadmapBookmark(models.Model):
    """A user bookmarking a roadmap."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    roadmap = models.ForeignKey(
        Roadmap,
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Roadmap Bookmark"
        verbose_name_plural = "Roadmap Bookmarks"
        unique_together = [("user", "roadmap")]
        indexes = [
            models.Index(fields=["user", "roadmap"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} ▶ {self.roadmap}"


class Node(models.Model):
    """A single topic/step within a roadmap."""

    class Status(models.TextChoices):
        LOCKED = "LOCKED", "Locked"
        UNLOCKED = "UNLOCKED", "Unlocked"
        COMPLETED = "COMPLETED", "Completed"

    roadmap = models.ForeignKey(
        Roadmap,
        on_delete=models.CASCADE,
        related_name="nodes",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Ascending order within the roadmap. Lower = earlier.",
    )
    quiz_pass_mark = models.PositiveSmallIntegerField(
        default=60,
        help_text="Minimum percentage score to pass this node's quiz.",
    )

    class Meta:
        verbose_name = "Node"
        verbose_name_plural = "Nodes"
        ordering = ["roadmap", "order"]
        unique_together = [("roadmap", "order"), ("roadmap", "slug")]
        indexes = [
            models.Index(fields=["roadmap", "order"]),
        ]

    def __str__(self) -> str:
        return f"{self.roadmap.title} › {self.order}. {self.title}"


class Video(models.Model):
    """A YouTube video attached to a node."""

    node = models.ForeignKey(
        Node,
        on_delete=models.CASCADE,
        related_name="videos",
    )
    youtube_id = models.CharField(max_length=20, help_text="YouTube video ID (11-char string).")
    title = models.CharField(max_length=300)
    channel_name = models.CharField(max_length=200, blank=True)
    duration_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Total duration in seconds (fetched from YouTube Data API).",
    )
    order = models.PositiveSmallIntegerField(default=0, help_text="Display order within the node.")
    is_embeddable = models.BooleanField(default=True, help_text="Whether the video can be embedded.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Video"
        verbose_name_plural = "Videos"
        ordering = ["node", "order"]
        unique_together = [("node", "order")]
        indexes = [
            models.Index(fields=["node", "order"]),
            models.Index(fields=["youtube_id"]),
        ]

    def __str__(self) -> str:
        return f"[{self.youtube_id}] {self.title}"
