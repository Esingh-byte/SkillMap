r"""
Management command: demo_fastforward

Enrolls a user in a roadmap (if needed), completes all nodes prior to the
target node order via ``complete_node``, and leaves the target node UNLOCKED.
Refuses to run unless ``settings.DEBUG`` is True.

Usage:
    .\.venv\Scripts\python.exe manage.py demo_fastforward <username> <roadmap_slug> <node_order>
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from progress.models import NodeProgress
from progress.services import complete_node, enroll_user
from roadmaps.models import Roadmap


class Command(BaseCommand):
    help = "Fast-forward a user's progress on a roadmap up to <node_order> (DEBUG only)."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Username of the student account.")
        parser.add_argument("roadmap_slug", help="Slug of the target roadmap.")
        parser.add_argument(
            "node_order",
            type=int,
            help="Order of the target node to leave UNLOCKED (completes all earlier nodes).",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "DEBUG", False):
            raise CommandError(
                "Refusing to run demo_fastforward when settings.DEBUG is False."
            )

        username = options["username"]
        roadmap_slug = options["roadmap_slug"]
        node_order = options["node_order"]

        user = User.objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"User '{username}' not found.")

        roadmap = Roadmap.objects.filter(slug=roadmap_slug).first()
        if roadmap is None:
            raise CommandError(f"Roadmap '{roadmap_slug}' not found.")

        target_node = roadmap.nodes.filter(order=node_order).first()
        if target_node is None:
            raise CommandError(
                f"Node with order={node_order} not found in roadmap '{roadmap_slug}'."
            )

        with transaction.atomic():
            enroll_user(user, roadmap)
            earlier_nodes = list(
                roadmap.nodes.filter(order__lt=node_order).order_by("order", "pk")
            )
            for node in earlier_nodes:
                complete_node(user, node)

        target_progress = NodeProgress.objects.get(user=user, node=target_node)
        self.stdout.write(
            self.style.SUCCESS(
                f"Fast-forwarded '{user.username}' on '{roadmap.slug}': "
                f"completed {len(earlier_nodes)} node(s); "
                f"node #{target_node.order} ('{target_node.title}') is {target_progress.status}."
            )
        )
