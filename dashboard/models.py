from django.db import models
from django.conf import settings


class Badge(models.Model):
    """An achievement badge that can be awarded to users."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=100,
        blank=True,
        help_text="CSS class or emoji for the badge icon.",
    )

    class Meta:
        verbose_name = "Badge"
        verbose_name_plural = "Badges"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
        ]

    def __str__(self) -> str:
        return self.name


class UserBadge(models.Model):
    """Junction table recording which badges a user has earned."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_badges",
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name="user_badges",
    )
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "User Badge"
        verbose_name_plural = "User Badges"
        unique_together = [("user", "badge")]
        ordering = ["-awarded_at"]
        indexes = [
            models.Index(fields=["user", "badge"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} earned {self.badge}"
