from django.urls import path
from . import views

app_name = "roadmaps"

urlpatterns = [
    path("", views.roadmap_list, name="list"),
    path("saved/", views.saved_roadmaps, name="saved"),
    path("<slug:slug>/", views.roadmap_detail, name="detail"),
    path("<slug:slug>/bookmark/", views.toggle_bookmark, name="bookmark"),
    path("<slug:roadmap_slug>/<slug:node_slug>/", views.node_detail, name="node_detail"),
]
