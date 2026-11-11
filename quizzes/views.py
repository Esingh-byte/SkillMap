from django.http import HttpResponse


def quiz_attempt(request, quiz_pk):
    return HttpResponse("quiz attempt – coming soon")
