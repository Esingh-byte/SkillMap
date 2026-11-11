from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from progress.models import NodeProgress
from progress.services import (
    InvalidAnswerError,
    NodeLockedError,
    VideoCheckNotPassedError,
    submit_quiz,
)
from roadmaplearn.http import BadRequest, json_error, parse_json
from roadmaps.models import Node


@login_required
@require_POST
def submit(request, node_id):
    node = get_object_or_404(Node, pk=node_id)
    try:
        data = parse_json(request)
    except BadRequest as exc:
        return json_error(str(exc), 400)
    answers = data.get("answers")
    if not isinstance(answers, dict):
        return json_error('"answers" must be an object of question_id: choice_id.', 400)

    user = request.user
    xp_before = user.xp
    try:
        attempt = submit_quiz(user, node, answers)
    except NodeLockedError as exc:
        return json_error(str(exc), 403)
    except VideoCheckNotPassedError as exc:
        return json_error(str(exc), 403)
    except InvalidAnswerError as exc:
        return json_error(str(exc), 400)

    user.refresh_from_db(fields=["xp"])
    completed = NodeProgress.objects.filter(
        user=user, node=node, status=NodeProgress.Status.COMPLETED
    ).exists()
    return JsonResponse(
        {
            "passed": attempt.passed,
            "score_percent": float(attempt.score_percent),
            "node_completed": completed,
            "xp_awarded": user.xp - xp_before,
        }
    )
