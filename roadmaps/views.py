from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from notes.models import Note
from progress.models import NodeProgress, VideoProgress
from progress.services import (
    enroll_user,
    node_statuses,
    roadmap_progress,
    video_check_passed,
)

from .models import Category, Node, Roadmap
from .services import (
    get_bookmarked_roadmap_ids,
    get_saved_roadmaps,
    search_roadmaps,
    toggle_roadmap_bookmark,
)

ROADMAPS_PER_PAGE = 12


def roadmap_list(request):
    q = (request.GET.get("q") or "").strip()
    selected = (request.GET.get("category") or "").strip()
    qs = search_roadmaps(q=q, category=selected or None)

    paginator = Paginator(qs, ROADMAPS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "roadmaps/roadmap_list.html",
        {
            "roadmaps": page_obj,
            "page_obj": page_obj,
            "categories": Category.objects.order_by("name"),
            "selected_category": selected,
            "q": q,
            "bookmarked_ids": get_bookmarked_roadmap_ids(request.user),
        },
    )


@login_required
def saved_roadmaps(request):
    roadmaps = list(get_saved_roadmaps(request.user))
    bookmarked_ids = {r.pk for r in roadmaps}
    return render(
        request,
        "roadmaps/saved_roadmaps.html",
        {
            "roadmaps": roadmaps,
            "bookmarked_ids": bookmarked_ids,
        },
    )


@login_required
@require_POST
def toggle_bookmark(request, slug):
    roadmap = get_object_or_404(Roadmap, slug=slug, is_published=True)
    is_bookmarked = toggle_roadmap_bookmark(request.user, roadmap)

    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "roadmaps/_bookmark_button.html",
            {
                "roadmap": roadmap,
                "is_bookmarked": is_bookmarked,
            },
        )

    if is_bookmarked:
        messages.success(request, f"Saved '{roadmap.title}' to your bookmarks.")
    else:
        messages.info(request, f"Removed '{roadmap.title}' from your saved roadmaps.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or ""
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(reverse("roadmaps:detail", args=[roadmap.slug]))


@login_required
def roadmap_detail(request, slug):
    roadmap = get_object_or_404(Roadmap, slug=slug, is_published=True)
    enroll_user(request.user, roadmap)  # idempotent
    statuses = node_statuses(request.user, roadmap)
    nodes = [
        {"node": n, "status": statuses[n.pk]}
        for n in roadmap.nodes.order_by("order", "pk")
    ]
    bookmarked_ids = get_bookmarked_roadmap_ids(request.user)
    return render(
        request,
        "roadmaps/roadmap_detail.html",
        {
            "roadmap": roadmap,
            "nodes": nodes,
            "progress": roadmap_progress(request.user, roadmap),
            "is_bookmarked": roadmap.pk in bookmarked_ids,
            "bookmarked_ids": bookmarked_ids,
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
