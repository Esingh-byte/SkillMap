from django.db import models
from django.conf import settings


class Note(models.Model):
    """Personal notes written by a user for a specific node."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    node = models.ForeignKey(
        "roadmaps.Node",
        on_delete=models.CASCADE,
        related_name="notes",
    )
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Note"
        verbose_name_plural = "Notes"
        unique_together = [("user", "node")]
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "node"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self) -> str:
        snippet = self.content[:50] if self.content else "(empty)"
        return f"{self.user} | {self.node} | {snippet}"
