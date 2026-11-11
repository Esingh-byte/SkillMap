from django.urls import path
from . import views

app_name = "quizzes"

urlpatterns = [
    path("<int:quiz_pk>/attempt/", views.quiz_attempt, name="attempt"),
]
