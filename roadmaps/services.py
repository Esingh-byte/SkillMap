"""
Business-logic services for the roadmaps app.
Roadmap retrieval, search, and bookmark helpers.
"""
from __future__ import annotations

from typing import Optional

from django.db.models import Case, IntegerField, Q, QuerySet, Value, When

from .models import Roadmap, RoadmapBookmark


def search_roadmaps(
    q: Optional[str] = "",
    category: Optional[str] = None,
) -> QuerySet[Roadmap]:
    """
    Return published roadmaps matching optional search query ``q`` and optional
    category slug ``category``.

    * Case-insensitive match across roadmap title, description, category name,
      and node titles.
    * Distinct results (no duplicates when multiple nodes match).
    * Unpublished roadmaps are never returned.
    * Title matches are ranked above description/category/node-only matches,
      then ordered alphabetically by title.
    """
    qs = Roadmap.objects.filter(is_published=True).select_related("category")

    cat_slug = (category or "").strip()
    if cat_slug:
        qs = qs.filter(category__slug=cat_slug)

    query = (q or "").strip()
    if query:
        qs = (
            qs.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(category__name__icontains=query)
                | Q(nodes__title__icontains=query)
            )
            .annotate(
                title_match=Case(
                    When(title__icontains=query, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
            .distinct()
            .order_by("title_match", "title", "pk")
        )
    else:
        qs = qs.order_by("title", "pk")

    return qs


def toggle_roadmap_bookmark(user, roadmap: Roadmap) -> bool:
    """
    Toggle a bookmark on a published ``roadmap`` for ``user``.
    Returns True if the roadmap is now bookmarked ("Saved"), or False if removed.
    Raises ValueError if ``roadmap`` is not published.
    """
    if not roadmap.is_published:
        raise ValueError("Cannot bookmark an unpublished roadmap.")

    existing = RoadmapBookmark.objects.filter(user=user, roadmap=roadmap).first()
    if existing is not None:
        existing.delete()
        return False

    RoadmapBookmark.objects.create(user=user, roadmap=roadmap)
    return True


def get_bookmarked_roadmap_ids(user) -> set[int]:
    """Return the set of published roadmap IDs bookmarked by ``user``."""
    if user is None or not getattr(user, "is_authenticated", False):
        return set()
    return set(
        RoadmapBookmark.objects.filter(
            user=user, roadmap__is_published=True
        ).values_list("roadmap_id", flat=True)
    )


def get_saved_roadmaps(user) -> QuerySet[Roadmap]:
    """Return published roadmaps bookmarked by ``user``, newest bookmark first."""
    return (
        Roadmap.objects.filter(is_published=True, bookmarks__user=user)
        .select_related("category")
        .order_by("-bookmarks__created_at", "title")
    )
