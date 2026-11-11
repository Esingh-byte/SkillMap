from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from roadmaplearn.http import BadRequest, json_error, parse_json
from roadmaps.models import Node

from .services import save_note


@login_required
@require_POST
def save(request, node_id):
    node = get_object_or_404(Node, pk=node_id)
    if request.content_type == "application/json":
        try:
            content = parse_json(request).get("content")
        except BadRequest as exc:
            return json_error(str(exc), 400)
    else:
        content = request.POST.get("content")
    if not isinstance(content, str):
        return json_error('"content" must be a string.', 400)

    note = save_note(request.user, node, content)
    return JsonResponse(
        {"status": "saved", "updated_at": timezone.localtime(note.updated_at).isoformat()}
    )
