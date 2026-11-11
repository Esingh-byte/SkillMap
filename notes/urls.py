from django.urls import path
from . import views

app_name = "notes"

urlpatterns = [
    path("<int:node_pk>/", views.note_edit, name="edit"),
]
