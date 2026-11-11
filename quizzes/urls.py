from django.urls import path
from . import views

app_name = "quizzes"

urlpatterns = [
    path("<int:node_id>/submit/", views.submit, name="submit"),
]
