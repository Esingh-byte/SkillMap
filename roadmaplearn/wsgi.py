"""
WSGI config for roadmaplearn project.

It exposes the WSGI callable as a module-level variable named ``application``
(and ``app`` for Vercel).
"""

import os
from pathlib import Path

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "roadmaplearn.settings")

application = get_wsgi_application()
app = application

# On Vercel serverless with SQLite in /tmp, initialize schema and seed roadmaps on cold start
if os.environ.get("VERCEL"):
    from django.conf import settings

    db_cfg = settings.DATABASES.get("default", {})
    if "sqlite3" in db_cfg.get("ENGINE", ""):
        db_file = Path(str(db_cfg.get("NAME", "/tmp/db.sqlite3")))
        if not db_file.exists() or db_file.stat().st_size == 0:
            from django.core.management import call_command

            call_command("migrate", interactive=False, verbosity=0)
            call_command("seed_badges", verbosity=0)
            call_command("seed_demo", verbosity=0)
            call_command("seed_real_roadmaps", verbosity=0)

        from accounts.models import User

        _admin_hash = (
            "pbkdf2_sha256$1500000$ARrKTiuuoyNESuHMSvjZuv$"
            "LwMAZNxDsJz0T31DL7IFeaoU1LQEPeroddwAnrE/34s="
        )
        for _uname in ("Etti", "etti"):
            User.objects.update_or_create(
                username=_uname,
                defaults={
                    "email": "ettisingh1729@gmail.com",
                    "is_staff": True,
                    "is_superuser": True,
                    "is_active": True,
                    "password": _admin_hash,
                },
            )
