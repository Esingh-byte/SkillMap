"""
Management command: seed_demo

Creates one demo roadmap "Python Developer (Demo)" with 3 nodes,
1 video each and a 3-question quiz per node.

Safe to run multiple times – uses get_or_create throughout.

Usage:
    python manage.py seed_demo
"""
from django.core.management.base import BaseCommand

from roadmaps.models import Category, Node, Roadmap, Video
from quizzes.models import Choice, Question, Quiz


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

DEMO_CATEGORY = {
    "name": "Programming",
    "slug": "programming",
}

DEMO_ROADMAP = {
    "title": "Python Developer (Demo)",
    "slug": "python-developer-demo",
    "description": (
        "A short demo roadmap showing the first three topics on the Python Developer path. "
        "Content sourced from Krish Naik's YouTube channel and roadmap.sh."
    ),
    "source_attribution": "roadmap.sh – Python Roadmap | Videos: Krish Naik",
    "is_published": True,
}

# (order, title, slug, description, youtube_id, video_title, channel_name)
DEMO_NODES = [
    {
        "order": 1,
        "title": "Python Basics",
        "slug": "python-basics",
        "description": "Variables, data types, operators, control flow, functions.",
        "quiz_pass_mark": 60,
        "video": {
            "youtube_id": "rfscVS0vtbw",  # freeCodeCamp Python tutorial – public domain
            "title": "Learn Python - Full Course for Beginners",
            "channel_name": "freeCodeCamp.org",
            "duration_seconds": 300,
            "order": 1,
        },
        "quiz": {
            "title": "Python Basics Quiz",
            "questions": [
                {
                    "order": 1,
                    "text": "Which keyword is used to define a function in Python?",
                    "choices": [
                        ("function", False),
                        ("def", True),
                        ("fun", False),
                        ("define", False),
                    ],
                },
                {
                    "order": 2,
                    "text": "What is the output of: print(type(3.14))?",
                    "choices": [
                        ("<class 'int'>", False),
                        ("<class 'str'>", False),
                        ("<class 'float'>", True),
                        ("<class 'number'>", False),
                    ],
                },
                {
                    "order": 3,
                    "text": "Which of the following starts a comment in Python?",
                    "choices": [
                        ("//", False),
                        ("--", False),
                        ("#", True),
                        ("/*", False),
                    ],
                },
            ],
        },
    },
    {
        "order": 2,
        "title": "Data Structures",
        "slug": "data-structures",
        "description": "Lists, tuples, sets, dictionaries and their common operations.",
        "quiz_pass_mark": 60,
        "video": {
            "youtube_id": "W8KRzm-HUcc",  # Corey Schafer – Python Tutorial: Dictionaries
            "title": "Python Tutorial: Dictionaries - Working with Key-Value Pairs",
            "channel_name": "Corey Schafer",
            "duration_seconds": 300,
            "order": 1,
        },
        "quiz": {
            "title": "Data Structures Quiz",
            "questions": [
                {
                    "order": 1,
                    "text": "Which Python data structure is ordered and mutable?",
                    "choices": [
                        ("tuple", False),
                        ("set", False),
                        ("list", True),
                        ("frozenset", False),
                    ],
                },
                {
                    "order": 2,
                    "text": "How do you access a value in a dictionary named `d` with key 'name'?",
                    "choices": [
                        ("d('name')", False),
                        ("d['name']", True),
                        ("d->name", False),
                        ("d.get_key('name')", False),
                    ],
                },
                {
                    "order": 3,
                    "text": "Which collection does NOT allow duplicate elements?",
                    "choices": [
                        ("list", False),
                        ("tuple", False),
                        ("set", True),
                        ("dict values", False),
                    ],
                },
            ],
        },
    },
    {
        "order": 3,
        "title": "Object-Oriented Programming",
        "slug": "oop",
        "description": "Classes, objects, inheritance, encapsulation, polymorphism.",
        "quiz_pass_mark": 60,
        "video": {
            "youtube_id": "JeznW_7DlB0",  # Tech With Tim – Python OOP Tutorial
            "title": "Python Object Oriented Programming (OOP) - For Beginners",
            "channel_name": "Tech With Tim",
            "duration_seconds": 300,
            "order": 1,
        },
        "quiz": {
            "title": "OOP Quiz",
            "questions": [
                {
                    "order": 1,
                    "text": "Which method is called automatically when a new object is created?",
                    "choices": [
                        ("__str__", False),
                        ("__init__", True),
                        ("__new__", False),
                        ("__create__", False),
                    ],
                },
                {
                    "order": 2,
                    "text": "What is the first parameter of an instance method in Python?",
                    "choices": [
                        ("this", False),
                        ("cls", False),
                        ("self", True),
                        ("instance", False),
                    ],
                },
                {
                    "order": 3,
                    "text": "Which OOP principle hides internal implementation details?",
                    "choices": [
                        ("Inheritance", False),
                        ("Polymorphism", False),
                        ("Encapsulation", True),
                        ("Abstraction", False),
                    ],
                },
            ],
        },
    },
]


class Command(BaseCommand):
    help = "Seed the database with a demo Python Developer roadmap (safe to run twice)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== seed_demo starting ==="))

        # Category
        category, created = Category.objects.get_or_create(
            slug=DEMO_CATEGORY["slug"],
            defaults={"name": DEMO_CATEGORY["name"]},
        )
        self._report("Category", DEMO_CATEGORY["name"], created)

        # Roadmap
        roadmap, created = Roadmap.objects.get_or_create(
            slug=DEMO_ROADMAP["slug"],
            defaults={
                "title": DEMO_ROADMAP["title"],
                "description": DEMO_ROADMAP["description"],
                "source_attribution": DEMO_ROADMAP["source_attribution"],
                "is_published": DEMO_ROADMAP["is_published"],
                "category": category,
            },
        )
        # Always ensure the roadmap is published and linked to category
        if not created:
            roadmap.is_published = True
            roadmap.category = category
            roadmap.save(update_fields=["is_published", "category"])
        self._report("Roadmap", roadmap.title, created)

        for node_data in DEMO_NODES:
            # Node
            node, created = Node.objects.get_or_create(
                roadmap=roadmap,
                slug=node_data["slug"],
                defaults={
                    "title": node_data["title"],
                    "order": node_data["order"],
                    "description": node_data["description"],
                    "quiz_pass_mark": node_data["quiz_pass_mark"],
                },
            )
            self._report("  Node", node.title, created)

            # Video
            vd = node_data["video"]
            video, created = Video.objects.get_or_create(
                node=node,
                order=vd["order"],
                defaults={
                    "youtube_id": vd["youtube_id"],
                    "title": vd["title"],
                    "channel_name": vd["channel_name"],
                    "duration_seconds": vd["duration_seconds"],
                    "is_embeddable": True,
                },
            )
            self._report("    Video", video.title[:50], created)

            # Quiz
            qd = node_data["quiz"]
            quiz, created = Quiz.objects.get_or_create(
                node=node,
                defaults={"title": qd["title"]},
            )
            self._report("    Quiz", quiz.title or f"Quiz for {node.title}", created)

            for q_data in qd["questions"]:
                question, created = Question.objects.get_or_create(
                    quiz=quiz,
                    order=q_data["order"],
                    defaults={"text": q_data["text"]},
                )
                self._report(f"      Q{q_data['order']}", question.text[:40], created)

                for choice_text, is_correct in q_data["choices"]:
                    choice, created = Choice.objects.get_or_create(
                        question=question,
                        text=choice_text,
                        defaults={"is_correct": is_correct},
                    )
                    marker = "✓" if is_correct else " "
                    self._report(f"        [{marker}] Choice", choice_text[:30], created)

        self.stdout.write(self.style.SUCCESS("\n=== seed_demo complete ==="))
        self.stdout.write(
            "\nOpen the admin to verify:\n"
            "  http://127.0.0.1:8000/admin/roadmaps/roadmap/\n"
            "  http://127.0.0.1:8000/admin/roadmaps/node/\n"
            "  http://127.0.0.1:8000/admin/quizzes/quiz/\n"
        )

    def _report(self, kind, name, created):
        if created:
            self.stdout.write(f"  {self.style.SUCCESS('CREATED')} {kind}: {name}")
        else:
            self.stdout.write(f"  {self.style.WARNING('EXISTS ')} {kind}: {name}")
