from django.http import HttpResponse
from django.views.decorators.http import require_POST


@require_POST
def heartbeat(request):
    return HttpResponse("heartbeat – coming soon")
