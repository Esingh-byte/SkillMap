from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render

from notes.models import Note
from progress.models import NodeProgress, VideoProgress
from progress.services import (
    enroll_user,
    node_statuses,
    roadmap_progress,
    video_check_passed,
)

from .models import Category, Node, Roadmap


def roadmap_list(request):
    roadmaps = Roadmap.objects.filter(is_published=True).select_related("category")
    selected = request.GET.get("category", "")
    if selected:
        roadmaps = roadmaps.filter(category__slug=selected)
    return render(
        request,
        "roadmaps/roadmap_list.html",
        {
            "roadmaps": roadmaps.order_by("title"),
            "categories": Category.objects.order_by("name"),
            "selected_category": selected,
        },
    )


@login_required
def roadmap_detail(request, slug):
    roadmap = get_object_or_404(Roadmap, slug=slug, is_published=True)
    enroll_user(request.user, roadmap)  # idempotent
    statuses = node_statuses(request.user, roadmap)
    nodes = [
        {"node": n, "status": statuses[n.pk]}
        for n in roadmap.nodes.order_by("order", "pk")
    ]
    return render(
        request,
        "roadmaps/roadmap_detail.html",
        {
            "roadmap": roadmap,
            "nodes": nodes,
            "progress": roadmap_progress(request.user, roadmap),
        },
    )


@login_required
def node_detail(request, roadmap_slug, node_slug):
    node = get_object_or_404(
        Node.objects.select_related("roadmap"),
        roadmap__slug=roadmap_slug,
        roadmap__is_published=True,
        slug=node_slug,
    )
    user = request.user
    node_progress = NodeProgress.objects.filter(user=user, node=node).first()
    if node_progress is None or node_progress.status == NodeProgress.Status.LOCKED:
        raise PermissionDenied("This node is locked or you are not enrolled.")

    videos = list(node.videos.filter(is_embeddable=True).order_by("order"))
    watched = dict(
        VideoProgress.objects.filter(user=user, video__in=videos).values_list(
            "video_id", "watched_seconds"
        )
    )
    video_rows = [
        {"video": v, "watched_seconds": min(watched.get(v.pk, 0), v.duration_seconds)}
        for v in videos
    ]
    note = Note.objects.filter(user=user, node=node).first()
    quiz = getattr(node, "quiz", None)
    questions = []
    video_passed = video_check_passed(user, node)
    if quiz is not None and video_passed:
        # Never expose is_correct to the client.
        questions = list(quiz.questions.order_by("order").prefetch_related("choices"))
    return render(
        request,
        "roadmaps/node_detail.html",
        {
            "node": node,
            "roadmap": node.roadmap,
            "status": node_progress.status,
            "videos": video_rows,
            "note": note,
            "has_quiz": bool(quiz and quiz.questions.exists()),
            "quiz": quiz,
            "questions": questions,
            "video_passed": video_passed,
            "quiz_passed": bool(
                quiz and quiz.attempts.filter(user=user, passed=True).exists()
            ),
        },
    )
