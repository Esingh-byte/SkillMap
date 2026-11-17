r"""
Management command: import_roadmap

Imports or updates a roadmap, its nodes, videos, and quizzes offline from a
roadmap JSON file and a previously dumped playlist JSON file.

Usage:
    .\.venv\Scripts\python.exe manage.py import_roadmap data/roadmaps/example.json [--dry-run] [--allow-non-embeddable]
"""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from progress.models import VideoProgress
from quizzes.models import Choice, Question, Quiz, QuizAttempt
from roadmaps.models import Category, Node, Roadmap, Video

REQUIRED_TOP_KEYS = (
    "slug",
    "title",
    "description",
    "category",
    "source_attribution",
    "playlist",
    "nodes",
)

REQUIRED_NODE_KEYS = (
    "title",
    "description",
    "videos",
)


def _resolve_playlist_path(playlist_ref: str, roadmap_file: Path) -> Path:
    """Resolve the playlist JSON path relative to CWD, BASE_DIR, or the roadmap JSON directory."""
    candidate = Path(playlist_ref)
    if candidate.is_file():
        return candidate

    base_dir_candidate = Path(settings.BASE_DIR) / playlist_ref
    if base_dir_candidate.is_file():
        return base_dir_candidate

    relative_to_roadmap = roadmap_file.parent / playlist_ref
    if relative_to_roadmap.is_file():
        return relative_to_roadmap

    return candidate


def validate_roadmap_spec(
    roadmap_data: dict,
    playlist_data: dict | None,
    allow_non_embeddable: bool = False,
) -> list[str]:
    """
    Validate the entire roadmap JSON and its referenced playlist JSON before any DB writes.
    Returns a list of human-readable validation error strings (empty if valid).
    """
    errors: list[str] = []

    if not isinstance(roadmap_data, dict):
        return ["Roadmap file root must be a JSON object."]

    for key in REQUIRED_TOP_KEYS:
        if key not in roadmap_data or roadmap_data[key] in (None, ""):
            errors.append(f"Missing required top-level key: '{key}'.")

    if "is_published" in roadmap_data and not isinstance(
        roadmap_data["is_published"], bool
    ):
            errors.append("Key 'is_published' must be a boolean.")

    playlist_by_pos: dict[int, dict] = {}
    if playlist_data is None:
        errors.append("Playlist file could not be loaded.")
    elif not isinstance(playlist_data, dict) or not isinstance(
        playlist_data.get("videos"), list
    ):
        errors.append("Playlist JSON must be an object containing a 'videos' list.")
    else:
        for v in playlist_data["videos"]:
            if isinstance(v, dict) and isinstance(v.get("position"), int):
                playlist_by_pos[v["position"]] = v

    nodes = roadmap_data.get("nodes")
    if not isinstance(nodes, list) or len(nodes) == 0:
        errors.append("'nodes' must be a non-empty list.")
        return errors

    seen_titles: set[str] = set()
    seen_slugs: set[str] = set()

    for n_idx, node in enumerate(nodes, start=1):
        if not isinstance(node, dict):
            errors.append(f"Node #{n_idx}: must be a JSON object.")
            continue

        node_label = node.get("title") or f"#{n_idx}"
        for n_key in REQUIRED_NODE_KEYS:
            if n_key not in node or node[n_key] is None:
                errors.append(f"Node '{node_label}': missing required key '{n_key}'.")

        raw_title = (node.get("title") or "").strip()
        if not raw_title:
            errors.append(f"Node #{n_idx}: 'title' cannot be blank.")
        else:
            norm_title = raw_title.lower()
            node_slug = slugify(raw_title)
            if not node_slug:
                errors.append(
                    f"Node '{raw_title}': title must produce a valid non-empty slug."
                )
            elif norm_title in seen_titles or node_slug in seen_slugs:
                errors.append(
                    f"Duplicate node title '{raw_title}' within roadmap file."
                )
            else:
                seen_titles.add(norm_title)
                seen_slugs.add(node_slug)

        videos = node.get("videos")
        if not isinstance(videos, list) or len(videos) == 0:
            errors.append(f"Node '{node_label}': must have at least 1 video.")
        elif playlist_data is not None:
            for pos in videos:
                if not isinstance(pos, int) or pos not in playlist_by_pos:
                    errors.append(
                        f"Node '{node_label}': video position {pos!r} does not exist in playlist."
                    )
                else:
                    p_vid = playlist_by_pos[pos]
                    if not p_vid.get("embeddable", True) and not allow_non_embeddable:
                        vid_id = p_vid.get("video_id", "unknown")
                        errors.append(
                            f"Node '{node_label}': video at position {pos} ({vid_id}) is non-embeddable "
                            "(pass --allow-non-embeddable to allow)."
                        )

        quiz_list = node.get("quiz")
        if quiz_list is not None:
            if not isinstance(quiz_list, list):
                errors.append(f"Node '{node_label}': 'quiz' must be a list of questions.")
            else:
                for q_idx, q in enumerate(quiz_list, start=1):
                    if not isinstance(q, dict):
                        errors.append(
                            f"Node '{node_label}' Q{q_idx}: question must be an object."
                        )
                        continue
                    q_text = (q.get("text") or "").strip()
                    if not q_text:
                        errors.append(
                            f"Node '{node_label}' Q{q_idx}: question 'text' is required."
                        )
                    choices = q.get("choices")
                    if not isinstance(choices, list) or len(choices) < 2:
                        errors.append(
                            f"Node '{node_label}' Q{q_idx}: must have at least 2 choices."
                        )
                        continue
                    correct_count = 0
                    for c_idx, c in enumerate(choices, start=1):
                        if not isinstance(c, dict) or not (c.get("text") or "").strip():
                            errors.append(
                                f"Node '{node_label}' Q{q_idx} choice #{c_idx}: choice 'text' is required."
                            )
                        if isinstance(c, dict) and c.get("correct") is True:
                            correct_count += 1
                    if correct_count != 1:
                        errors.append(
                            f"Node '{node_label}' Q{q_idx}: must have exactly 1 correct choice (found {correct_count})."
                        )

    return errors


class Command(BaseCommand):
    help = "Validate and import a roadmap JSON file and its offline playlist dump."

    def add_arguments(self, parser):
        parser.add_argument(
            "roadmap_file",
            help="Path to the roadmap JSON file (e.g. data/roadmaps/example.json).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and print the import plan without writing to the database.",
        )
        parser.add_argument(
            "--allow-non-embeddable",
            action="store_true",
            help="Allow importing videos marked embeddable=false (stored with is_embeddable=False).",
        )

    def handle(self, *args, **options):
        roadmap_path = Path(options["roadmap_file"])
        dry_run = bool(options["dry_run"])
        allow_non_embeddable = bool(options["allow_non_embeddable"])

        if not roadmap_path.is_file():
            raise CommandError(f"Roadmap file not found: {roadmap_path}")

        try:
            roadmap_data = json.loads(roadmap_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {roadmap_path}: {exc}") from None

        playlist_data = None
        playlist_ref = (
            roadmap_data.get("playlist") if isinstance(roadmap_data, dict) else None
        )
        if playlist_ref:
            playlist_path = _resolve_playlist_path(str(playlist_ref), roadmap_path)
            if playlist_path.is_file():
                try:
                    playlist_data = json.loads(
                        playlist_path.read_text(encoding="utf-8")
                    )
                except json.JSONDecodeError as exc:
                    raise CommandError(
                        f"Invalid JSON in playlist file {playlist_path}: {exc}"
                    ) from None

        errors = validate_roadmap_spec(
            roadmap_data,
            playlist_data,
            allow_non_embeddable=allow_non_embeddable,
        )
        if errors:
            bullet_list = "\n".join(f"  - {err}" for err in errors)
            raise CommandError(f"Validation failed with {len(errors)} error(s):\n{bullet_list}")

        playlist_by_pos: dict[int, dict] = {
            v["position"]: v for v in playlist_data["videos"]
        }

        if dry_run:
            self._print_dry_run_plan(roadmap_data, playlist_by_pos)
            return

        counts = {"created": 0, "updated": 0, "unchanged": 0}

        with transaction.atomic():
            # 1. Category
            cat_raw = roadmap_data["category"]
            if isinstance(cat_raw, dict):
                cat_name = str(cat_raw.get("name") or cat_raw.get("slug")).strip()
                cat_slug = str(cat_raw.get("slug") or slugify(cat_name)).strip()
            else:
                cat_name = str(cat_raw).strip()
                cat_slug = slugify(cat_name)

            category, cat_created = Category.objects.get_or_create(
                slug=cat_slug,
                defaults={"name": cat_name},
            )
            if cat_created:
                counts["created"] += 1
            elif category.name != cat_name:
                category.name = cat_name
                category.save(update_fields=["name"])
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1

            # 2. Roadmap
            rm_slug = str(roadmap_data["slug"]).strip()
            rm_defaults = {
                "title": str(roadmap_data["title"]).strip(),
                "description": str(roadmap_data["description"]),
                "category": category,
                "source_attribution": str(roadmap_data["source_attribution"]),
                "is_published": bool(roadmap_data.get("is_published", False)),
            }
            roadmap, rm_created = Roadmap.objects.get_or_create(
                slug=rm_slug,
                defaults=rm_defaults,
            )
            if rm_created:
                counts["created"] += 1
            else:
                rm_changed = False
                for field, val in rm_defaults.items():
                    if getattr(roadmap, field) != val:
                        setattr(roadmap, field, val)
                        rm_changed = True
                if rm_changed:
                    roadmap.save()
                    counts["updated"] += 1
                else:
                    counts["unchanged"] += 1

            # 3. Nodes — avoid unique_together(roadmap, order) collisions on reorder
            existing_nodes = {
                n.slug: n for n in Node.objects.filter(roadmap=roadmap).order_by("order", "pk")
            }
            orig_node_state = {
                slug: (n.title, n.description, n.order, n.quiz_pass_mark)
                for slug, n in existing_nodes.items()
            }

            if existing_nodes:
                for offset, existing_node in enumerate(existing_nodes.values(), start=1):
                    Node.objects.filter(pk=existing_node.pk).update(order=10000 + offset)

            for order_idx, node_spec in enumerate(roadmap_data["nodes"], start=1):
                node_title = str(node_spec["title"]).strip()
                node_slug = slugify(node_title)
                node_desc = str(node_spec.get("description") or "")
                pass_mark = int(node_spec.get("quiz_pass_mark", 60))

                if node_slug in existing_nodes:
                    node = existing_nodes[node_slug]
                    node.title = node_title
                    node.description = node_desc
                    node.order = order_idx
                    node.quiz_pass_mark = pass_mark
                    node.save()

                    if orig_node_state[node_slug] == (
                        node_title,
                        node_desc,
                        order_idx,
                        pass_mark,
                    ):
                        counts["unchanged"] += 1
                    else:
                        counts["updated"] += 1
                else:
                    node = Node.objects.create(
                        roadmap=roadmap,
                        slug=node_slug,
                        title=node_title,
                        description=node_desc,
                        order=order_idx,
                        quiz_pass_mark=pass_mark,
                    )
                    counts["created"] += 1

                # 4. Videos for this node
                self._sync_node_videos(node, node_spec["videos"], playlist_by_pos, counts)

                # 5. Quiz for this node
                if "quiz" in node_spec and node_spec["quiz"] is not None:
                    self._sync_node_quiz(node, node_spec["quiz"], counts)

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete for roadmap '{roadmap.slug}': "
                f"created={counts['created']}, updated={counts['updated']}, unchanged={counts['unchanged']}"
            )
        )

    def _sync_node_videos(
        self,
        node: Node,
        positions: list[int],
        playlist_by_pos: dict[int, dict],
        counts: dict[str, int],
    ) -> None:
        existing_videos = {
            v.youtube_id: v for v in Video.objects.filter(node=node).order_by("order", "pk")
        }
        orig_video_state = {
            yt_id: (
                v.title,
                v.channel_name,
                v.duration_seconds,
                v.order,
                v.is_embeddable,
            )
            for yt_id, v in existing_videos.items()
        }

        target_specs = []
        target_yt_ids = set()
        for v_order, pos in enumerate(positions, start=1):
            p_vid = playlist_by_pos[pos]
            yt_id = str(p_vid["video_id"])
            target_yt_ids.add(yt_id)
            target_specs.append(
                (
                    v_order,
                    yt_id,
                    str(p_vid["title"]),
                    str(p_vid.get("channel") or ""),
                    int(p_vid["duration_seconds"]),
                    bool(p_vid.get("embeddable", True)),
                )
            )

        # Handle videos removed from the node spec
        kept_With_progress: list[Video] = []
        for yt_id, v in list(existing_videos.items()):
            if yt_id not in target_yt_ids:
                if VideoProgress.objects.filter(video=v).exists():
                    self.stdout.write(
                        self.style.WARNING(
                            f"WARNING: Video '{v.youtube_id}' on node '{node.title}' has student "
                            "watch progress; keeping video instead of deleting."
                        )
                    )
                    kept_With_progress.append(v)
                else:
                    v.delete()
                    del existing_videos[yt_id]

        # Move remaining existing videos on this node to temporary high order to avoid (node, order) clash
        for offset, v in enumerate(existing_videos.values(), start=1):
            Video.objects.filter(pk=v.pk).update(order=10000 + offset)

        for v_order, yt_id, v_title, v_channel, v_duration, v_embeddable in target_specs:
            video, v_created = Video.objects.update_or_create(
                node=node,
                youtube_id=yt_id,
                defaults={
                    "title": v_title,
                    "channel_name": v_channel,
                    "duration_seconds": v_duration,
                    "order": v_order,
                    "is_embeddable": v_embeddable,
                },
            )
            if v_created:
                counts["created"] += 1
            elif orig_video_state.get(yt_id) == (
                v_title,
                v_channel,
                v_duration,
                v_order,
                v_embeddable,
            ):
                counts["unchanged"] += 1
            else:
                counts["updated"] += 1

        # Place any preserved progress-bearing videos after the active videos
        for extra_idx, v in enumerate(kept_With_progress, start=len(target_specs) + 1):
            Video.objects.filter(pk=v.pk).update(order=extra_idx)

    def _sync_node_quiz(
        self,
        node: Node,
        quiz_questions: list[dict],
        counts: dict[str, int],
    ) -> None:
        desired_spec = [
            (
                q_idx,
                str(q["text"]).strip(),
                [
                    (str(c["text"]).strip(), bool(c.get("correct", False)))
                    for c in q["choices"]
                ],
            )
            for q_idx, q in enumerate(quiz_questions, start=1)
        ]

        quiz = Quiz.objects.filter(node=node).first()
        if quiz is None:
            quiz = Quiz.objects.create(node=node, title=f"{node.title} Quiz")
            self._build_quiz_questions(quiz, desired_spec)
            counts["created"] += 1
            return

        if QuizAttempt.objects.filter(quiz=quiz).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"WARNING: Quiz for node '{node.title}' has existing student attempts; "
                    "skipping quiz update."
                )
            )
            counts["unchanged"] += 1
            return

        current_spec = [
            (
                q.order,
                q.text,
                [(c.text, c.is_correct) for c in q.choices.order_by("pk")],
            )
            for q in quiz.questions.order_by("order", "pk")
        ]

        if current_spec == desired_spec:
            counts["unchanged"] += 1
            return

        quiz.questions.all().delete()
        self._build_quiz_questions(quiz, desired_spec)
        counts["updated"] += 1

    @staticmethod
    def _build_quiz_questions(quiz: Quiz, desired_spec: list[tuple]) -> None:
        for q_order, q_text, choices_spec in desired_spec:
            question = Question.objects.create(
                quiz=quiz,
                order=q_order,
                text=q_text,
            )
            for c_text, is_correct in choices_spec:
                Choice.objects.create(
                    question=question,
                    text=c_text,
                    is_correct=is_correct,
                )

    def _print_dry_run_plan(
        self,
        roadmap_data: dict,
        playlist_by_pos: dict[int, dict],
    ) -> None:
        nodes = roadmap_data["nodes"]
        total_videos = 0
        total_seconds = 0
        total_questions = 0

        self.stdout.write(
            f"DRY RUN — Roadmap: {roadmap_data['title']} (slug: {roadmap_data['slug']})"
        )
        for idx, n in enumerate(nodes, start=1):
            positions = n["videos"]
            node_seconds = sum(
                int(playlist_by_pos[pos]["duration_seconds"]) for pos in positions
            )
            node_minutes = node_seconds / 60.0
            q_count = len(n.get("quiz") or [])

            total_videos += len(positions)
            total_seconds += node_seconds
            total_questions += q_count

            self.stdout.write(
                f"  {idx:02d}. {n['title']} — {len(positions)} video(s), "
                f"{node_minutes:.1f} min, {q_count} question(s)"
            )

        self.stdout.write(
            f"Plan summary: {len(nodes)} node(s), {total_videos} video(s), "
            f"{total_seconds / 60.0:.1f} min total, {total_questions} question(s). "
            "No database changes written."
        )
