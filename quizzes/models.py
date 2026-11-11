from django.db import models
from django.conf import settings


class Quiz(models.Model):
    """A quiz attached to a node. One quiz per node."""

    node = models.OneToOneField(
        "roadmaps.Node",
        on_delete=models.CASCADE,
        related_name="quiz",
    )
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Quiz"
        verbose_name_plural = "Quizzes"

    def __str__(self) -> str:
        return f"Quiz – {self.node}"


class Question(models.Model):
    """A multiple-choice question belonging to a quiz."""

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    text = models.TextField(help_text="The question body.")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Question"
        verbose_name_plural = "Questions"
        ordering = ["quiz", "order"]
        indexes = [
            models.Index(fields=["quiz", "order"]),
        ]

    def __str__(self) -> str:
        return f"Q{self.order}: {self.text[:60]}"


class Choice(models.Model):
    """One answer choice for a question."""

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="choices",
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Choice"
        verbose_name_plural = "Choices"
        indexes = [
            models.Index(fields=["question", "is_correct"]),
        ]

    def __str__(self) -> str:
        marker = "✓" if self.is_correct else "✗"
        return f"{marker} {self.text[:60]}"


class QuizAttempt(models.Model):
    """Records one attempt at a node quiz by a user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    score_percent = models.PositiveSmallIntegerField(
        help_text="Score as a percentage (0–100).",
    )
    passed = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Quiz Attempt"
        verbose_name_plural = "Quiz Attempts"
        ordering = ["-attempted_at"]
        indexes = [
            models.Index(fields=["user", "quiz"]),
            models.Index(fields=["user", "passed"]),
        ]

    def __str__(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        return f"{self.user} | {self.quiz} | {self.score_percent}% [{status}]"
