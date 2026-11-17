import math

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from roadmaplearn.http import BadRequest, json_error, parse_json
from roadmaps.models import Video

from .models import NodeProgress
from .services import (
    NodeLockedError,
    NotEnrolledError,
    VideoNotEmbeddableError,
    node_video_totals,
    record_heartbeat,
    try_complete_node_without_quiz,
    video_check_passed,
)


@login_required
@require_POST
def heartbeat(request):
    try:
        data = parse_json(request)
        raw_vid = data["video_id"]
        raw_time = data["current_time"]
        raw_rate = data.get("playback_rate", 1.0)
        if (
            isinstance(raw_vid, bool)
            or isinstance(raw_time, bool)
            or isinstance(raw_rate, bool)
        ):
            raise ValueError("Booleans are not valid numbers.")
        video_id = int(raw_vid)
        current_time = float(raw_time)
        playback_rate = float(raw_rate)
    except BadRequest as exc:
        return json_error(str(exc), 400)
    except (KeyError, TypeError, ValueError, OverflowError):
        return json_error(
            "video_id, current_time and playback_rate must be numbers.", 400
        )
    if (
        not math.isfinite(current_time)
        or not math.isfinite(playback_rate)
        or current_time < 0
        or video_id <= 0
        or video_id > 2**63 - 1
    ):
        return json_error("Invalid numeric value.", 400)

    video = get_object_or_404(Video.objects.select_related("node__roadmap"), pk=video_id)
    node = video.node
    user = request.user
    try:
        record_heartbeat(user, video, current_time, playback_rate)
        passed = video_check_passed(user, node)
        if passed:
            try_complete_node_without_quiz(user, node)
    except (NotEnrolledError, NodeLockedError) as exc:
        return json_error(str(exc), 403)
    except VideoNotEmbeddableError as exc:
        return json_error(str(exc), 400)

    completed = NodeProgress.objects.filter(
        user=user, node=node, status=NodeProgress.Status.COMPLETED
    ).exists()
    totals = node_video_totals(user, node)
    return JsonResponse(
        {
            "status": "ok",
            "watched_seconds": totals["watched_seconds"],
            "duration_seconds": totals["duration_seconds"],
            "video_passed": passed,
            "node_completed": completed,
        }
    )
