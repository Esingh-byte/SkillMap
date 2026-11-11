from django.urls import path
from . import views

app_name = "progress"

urlpatterns = [
    path("heartbeat/", views.heartbeat, name="heartbeat"),
]
