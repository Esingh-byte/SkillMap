import json

from django.http import JsonResponse


class BadRequest(Exception):
    pass


def parse_json(request) -> dict:
    """Parse a JSON object body or raise BadRequest."""
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        raise BadRequest("Invalid JSON body.")
    if not isinstance(data, dict):
        raise BadRequest("JSON body must be an object.")
    return data


def json_error(message: str, status: int) -> JsonResponse:
    return JsonResponse({"status": "error", "error": message}, status=status)

