r"""
Management command: seed_badges

Idempotently seeds the 6 achievement badges into dashboard.Badge (matched by slug/code).

Usage:
    .\.venv\Scripts\python.exe manage.py seed_badges
"""
from django.core.management.base import BaseCommand

from dashboard.services import ensure_badges_seeded


class Command(BaseCommand):
    help = "Seed the 6 canonical achievement badges (safe to run multiple times)."

    def handle(self, *args, **options):
        results = ensure_badges_seeded()
        created_count = sum(1 for _, created in results if created)
        existing_count = len(results) - created_count

        for badge, created in results:
            status = "CREATED" if created else "EXISTS "
            self.stdout.write(f"  {status} Badge [{badge.slug}]: {badge.name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_badges complete: created={created_count}, existing={existing_count}"
            )
        )
