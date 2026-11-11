from django.http import HttpResponse


def roadmap_list(request):
    return HttpResponse("roadmap list – coming soon")


def roadmap_detail(request, slug):
    return HttpResponse("roadmap detail – coming soon")


def node_detail(request, roadmap_slug, node_slug):
    return HttpResponse("node detail – coming soon")
