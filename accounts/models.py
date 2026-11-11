from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extended user model with XP and streak tracking."""

    xp = models.PositiveIntegerField(default=0, help_text="Total experience points earned.")
    streak_days = models.PositiveIntegerField(default=0, help_text="Current daily learning streak.")
    last_active_date = models.DateField(null=True, blank=True, help_text="Date of last activity (for streak calculation).")

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:
        return f"{self.username} ({self.email})"
