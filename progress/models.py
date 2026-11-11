from django.db import models
from django.conf import settings


class NodeProgress(models.Model):
    """Tracks a user's progress through a single node (unlock/complete state)."""

    class Status(models.TextChoices):
        LOCKED = "LOCKED", "Locked"
        UNLOCKED = "UNLOCKED", "Unlocked"
        COMPLETED = "COMPLETED", "Completed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="node_progresses",
    )
    node = models.ForeignKey(
        "roadmaps.Node",
        on_delete=models.CASCADE,
        related_name="node_progresses",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.LOCKED)
    unlocked_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Node Progress"
        verbose_name_plural = "Node Progresses"
        unique_together = [("user", "node")]
        indexes = [
            models.Index(fields=["user", "node"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} | {self.node} | {self.status}"


class VideoProgress(models.Model):
    """
    Tracks a user's genuinely-watched time for a single video.

    Anti-cheat: watched_seconds is incremented server-side from heartbeats;
    the client total is never trusted directly.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="video_progresses",
    )
    video = models.ForeignKey(
        "roadmaps.Video",
        on_delete=models.CASCADE,
        related_name="video_progresses",
    )
    watched_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Cumulative server-verified watched seconds.",
    )
    last_position = models.FloatField(
        default=0.0,
        help_text="Last reported playback position (seconds) from client.",
    )
    last_heartbeat_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the most recent heartbeat received.",
    )

    class Meta:
        verbose_name = "Video Progress"
        verbose_name_plural = "Video Progresses"
        unique_together = [("user", "video")]
        indexes = [
            models.Index(fields=["user", "video"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} | {self.video} | {self.watched_seconds}s"


class RoadmapEnrollment(models.Model):
    """Records that a user has enrolled in a roadmap."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    roadmap = models.ForeignKey(
        "roadmaps.Roadmap",
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Roadmap Enrollment"
        verbose_name_plural = "Roadmap Enrollments"
        unique_together = [("user", "roadmap")]
        indexes = [
            models.Index(fields=["user", "roadmap"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} enrolled in {self.roadmap}"
