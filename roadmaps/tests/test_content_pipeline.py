import io
import json
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import User
from progress.models import VideoProgress
from quizzes.models import Choice, Question, Quiz, QuizAttempt
from roadmaps.management.commands.dump_playlist import (
    extract_playlist_id,
    parse_iso8601_duration,
)
from roadmaps.models import Category, Node, Roadmap, Video


class IsoDurationParserTests(TestCase):
    def test_standard_durations(self):
        self.assertEqual(parse_iso8601_duration("PT1H2M3S"), 3723)
        self.assertEqual(parse_iso8601_duration("PT45S"), 45)
        self.assertEqual(parse_iso8601_duration("PT15M"), 900)
        self.assertEqual(parse_iso8601_duration("PT2H"), 7200)
        self.assertEqual(parse_iso8601_duration("P1DT2H"), 93600)

    def test_live_zero_duration(self):
        self.assertEqual(parse_iso8601_duration("P0D"), 0)
        self.assertEqual(parse_iso8601_duration("PT0S"), 0)

    def test_invalid_durations_raise_value_error(self):
        for bad in ("", "P", "PT", "P1D2H", "1H2M", "PT-5S", None):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_iso8601_duration(bad)


class DumpPlaylistCommandTests(TestCase):
    SECRET_KEY_VAL = "AIzaSyFAKE_SECRET_UNIT_TEST_KEY_99999"

    def test_extract_playlist_id_variants_and_bad_inputs(self):
        self.assertEqual(
            extract_playlist_id("PLu0W_9lII9agwh1XjRt242xIpHhPT2llg"),
            "PLu0W_9lII9agwh1XjRt242xIpHhPT2llg",
        )
        self.assertEqual(
            extract_playlist_id(
                "https://www.youtube.com/playlist?list=PLu0W_9lII9agwh1XjRt242xIpHhPT2llg&si=abc"
            ),
            "PLu0W_9lII9agwh1XjRt242xIpHhPT2llg",
        )
        for bad in ("", "   ", "https://www.youtube.com/watch?v=abc", "bad id with spaces", "x"):
            with self.subTest(bad=bad):
                with self.assertRaises(CommandError):
                    extract_playlist_id(bad)

    @override_settings(YOUTUBE_API_KEY="")
    def test_missing_api_key_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "out.json"
            with self.assertRaisesMessage(CommandError, "YOUTUBE_API_KEY is not set"):
                call_command("dump_playlist", "PL12345", out=str(out_file))

    @override_settings(YOUTUBE_API_KEY=SECRET_KEY_VAL)
    @patch("roadmaps.management.commands.dump_playlist.fetch_json")
    def test_dump_across_two_pages_skips_private_and_preserves_positions(self, mock_fetch):
        # Page 1: position 0 (valid), position 1 (private video in playlistItems)
        page1 = {
            "nextPageToken": "TOKEN_PAGE_2",
            "items": [
                {
                    "snippet": {
                        "position": 0,
                        "title": "Intro Video",
                        "channelTitle": "Test Channel",
                        "resourceId": {"videoId": "vid_pos_1"},
                    },
                    "contentDetails": {"videoId": "vid_pos_1"},
                },
                {
                    "snippet": {
                        "position": 1,
                        "title": "Private video",
                        "channelTitle": "Test Channel",
                        "resourceId": {"videoId": "vid_pos_2"},
                    },
                    "contentDetails": {"videoId": "vid_pos_2"},
                },
            ],
        }
        # Page 2: position 2 (deleted: missing from videos.list), position 3 (valid, non-embeddable)
        page2 = {
            "items": [
                {
                    "snippet": {
                        "position": 2,
                        "title": "Ghost Video",
                        "channelTitle": "Test Channel",
                        "resourceId": {"videoId": "vid_pos_3"},
                    },
                    "contentDetails": {"videoId": "vid_pos_3"},
                },
                {
                    "snippet": {
                        "position": 3,
                        "title": "Deep Dive Video",
                        "channelTitle": "Test Channel",
                        "resourceId": {"videoId": "vid_pos_4"},
                    },
                    "contentDetails": {"videoId": "vid_pos_4"},
                },
            ],
        }
        # videos.list returns only vid_pos_1 and vid_pos_4 (vid_pos_3 comes back without data)
        videos_resp = {
            "items": [
                {
                    "id": "vid_pos_1",
                    "snippet": {"title": "Intro Video", "channelTitle": "Test Channel"},
                    "contentDetails": {"duration": "PT30M"},
                    "status": {"privacyStatus": "public", "embeddable": True},
                },
                {
                    "id": "vid_pos_4",
                    "snippet": {"title": "Deep Dive Video", "channelTitle": "Test Channel"},
                    "contentDetails": {"duration": "PT1H"},
                    "status": {"privacyStatus": "public", "embeddable": False},
                },
            ]
        }
        mock_fetch.side_effect = [page1, page2, videos_resp]

        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "dumped.json"
            call_command(
                "dump_playlist",
                "https://www.youtube.com/playlist?list=PLtestPlaylist99",
                out=str(out_file),
                stdout=stdout,
            )
            data = json.loads(out_file.read_text(encoding="utf-8"))
            raw_file_text = out_file.read_text(encoding="utf-8")

        output_str = stdout.getvalue()
        self.assertNotIn(self.SECRET_KEY_VAL, output_str)
        self.assertNotIn(self.SECRET_KEY_VAL, raw_file_text)

        self.assertEqual(data["playlist_id"], "PLtestPlaylist99")
        self.assertEqual(data["channel"], "Test Channel")
        # Original 1-based positions 1 and 4 are preserved despite positions 2 and 3 being skipped
        self.assertEqual([v["position"] for v in data["videos"]], [1, 4])
        self.assertEqual(data["videos"][0]["duration_seconds"], 1800)
        self.assertTrue(data["videos"][0]["embeddable"])
        self.assertEqual(data["videos"][1]["duration_seconds"], 3600)
        self.assertFalse(data["videos"][1]["embeddable"])

        self.assertIn("position 2", output_str)
        self.assertIn("position 3", output_str)
        self.assertIn("total=2, embeddable=1, non_embeddable=1, skipped=2, duration=1.50 hours", output_str)

    @override_settings(YOUTUBE_API_KEY=SECRET_KEY_VAL)
    @patch("roadmaps.management.commands.dump_playlist.fetch_json")
    def test_api_key_never_leaked_in_http_or_generic_errors(self, mock_fetch):
        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "out.json"

            # 403 error containing key in URL
            mock_fetch.side_effect = urllib.error.HTTPError(
                url=f"https://www.googleapis.com/youtube/v3/playlistItems?key={self.SECRET_KEY_VAL}",
                code=403,
                msg=f"Forbidden for key={self.SECRET_KEY_VAL}",
                hdrs=None,
                fp=None,
            )
            with self.assertRaises(CommandError) as ctx:
                call_command("dump_playlist", "PL12345", out=str(out_file))
            self.assertNotIn(self.SECRET_KEY_VAL, str(ctx.exception))
            self.assertIn("403", str(ctx.exception))

            # 404 bad playlist ID on server
            mock_fetch.side_effect = urllib.error.HTTPError(
                url=f"https://www.googleapis.com/youtube/v3/playlistItems?key={self.SECRET_KEY_VAL}",
                code=404,
                msg="Not Found",
                hdrs=None,
                fp=None,
            )
            with self.assertRaises(CommandError) as ctx404:
                call_command("dump_playlist", "PLbadId404", out=str(out_file))
            self.assertNotIn(self.SECRET_KEY_VAL, str(ctx404.exception))
            self.assertIn("404", str(ctx404.exception))

            # Unexpected runtime exception embedding key and URL
            mock_fetch.side_effect = RuntimeError(
                f"Failed GET https://example.com?key={self.SECRET_KEY_VAL}"
            )
            with self.assertRaises(CommandError) as ctx_err:
                call_command("dump_playlist", "PL12345", out=str(out_file))
            self.assertNotIn(self.SECRET_KEY_VAL, str(ctx_err.exception))


class ImportRoadmapCommandTests(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp_path = Path(self.tmpdir.name)

        self.playlist_path = self.tmp_path / "playlist.json"
        self.playlist_data = {
            "playlist_id": "PLtest001",
            "title": "Test Playlist",
            "channel": "Test Creator",
            "fetched_at": "2026-11-17T00:00:00+00:00",
            "videos": [
                {
                    "position": 1,
                    "video_id": "vid_001",
                    "title": "Video One",
                    "channel": "Test Creator",
                    "duration_seconds": 300,
                    "embeddable": True,
                },
                {
                    "position": 2,
                    "video_id": "vid_002",
                    "title": "Video Two",
                    "channel": "Test Creator",
                    "duration_seconds": 600,
                    "embeddable": True,
                },
                {
                    "position": 3,
                    "video_id": "vid_003",
                    "title": "Video Three",
                    "channel": "Test Creator",
                    "duration_seconds": 900,
                    "embeddable": True,
                },
                {
                    "position": 4,
                    "video_id": "vid_004_noembed",
                    "title": "Video Four Non-Embeddable",
                    "channel": "Test Creator",
                    "duration_seconds": 450,
                    "embeddable": False,
                },
            ],
        }
        self.playlist_path.write_text(json.dumps(self.playlist_data), encoding="utf-8")

        self.roadmap_path = self.tmp_path / "roadmap.json"
        self.roadmap_data = {
            "slug": "test-python-roadmap",
            "title": "Test Python Roadmap",
            "description": "Learn Python step by step.",
            "category": "Programming",
            "source_attribution": "roadmap.sh",
            "is_published": True,
            "playlist": str(self.playlist_path),
            "nodes": [
                {
                    "title": "Variables and Types",
                    "description": "First step.",
                    "section_label": "Basics",
                    "quiz_pass_mark": 60,
                    "videos": [1, 2],
                    "quiz": [
                        {
                            "text": "What is 1 + 1?",
                            "explanation": "Basic addition.",
                            "choices": [
                                {"text": "2", "correct": True},
                                {"text": "3", "correct": False},
                            ],
                        }
                    ],
                },
                {
                    "title": "Functions",
                    "description": "Second step.",
                    "quiz_pass_mark": 70,
                    "videos": [3],
                    "quiz": [
                        {
                            "text": "Which keyword defines a function?",
                            "choices": [
                                {"text": "def", "correct": True},
                                {"text": "fn", "correct": False},
                            ],
                        }
                    ],
                },
            ],
        }
        self.roadmap_path.write_text(json.dumps(self.roadmap_data), encoding="utf-8")

    def test_dry_run_writes_nothing(self):
        stdout = io.StringIO()
        call_command(
            "import_roadmap",
            str(self.roadmap_path),
            "--dry-run",
            stdout=stdout,
        )
        self.assertIn("DRY RUN", stdout.getvalue())
        self.assertEqual(Roadmap.objects.count(), 0)
        self.assertEqual(Node.objects.count(), 0)
        self.assertEqual(Video.objects.count(), 0)
        self.assertEqual(Quiz.objects.count(), 0)

    def test_first_import_counts_and_second_import_is_idempotent(self):
        # 1 Category + 1 Roadmap + 2 Nodes + 3 Videos + 2 Quizzes = 9 created
        stdout1 = io.StringIO()
        call_command("import_roadmap", str(self.roadmap_path), stdout=stdout1)
        self.assertIn("created=9, updated=0, unchanged=0", stdout1.getvalue())

        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Roadmap.objects.count(), 1)
        self.assertEqual(Node.objects.count(), 2)
        self.assertEqual(Video.objects.count(), 3)
        self.assertEqual(Quiz.objects.count(), 2)
        self.assertEqual(Question.objects.count(), 2)
        self.assertEqual(Choice.objects.count(), 4)

        # Second import: nothing created or updated
        stdout2 = io.StringIO()
        call_command("import_roadmap", str(self.roadmap_path), stdout=stdout2)
        self.assertIn("created=0, updated=0, unchanged=9", stdout2.getvalue())

    def test_validation_errors_reported_together(self):
        bad_roadmap = {
            "slug": "bad-roadmap",
            "title": "Bad Roadmap",
            "description": "Has multiple errors",
            "category": "Programming",
            "source_attribution": "roadmap.sh",
            "playlist": str(self.playlist_path),
            "nodes": [
                {
                    "title": "Duplicate Title",
                    "description": "Node 1",
                    "videos": [99, 4],  # 99 missing; 4 is non-embeddable
                    "quiz": [
                        {
                            "text": "Bad question with 2 correct answers",
                            "choices": [
                                {"text": "A", "correct": True},
                                {"text": "B", "correct": True},
                            ],
                        },
                        {
                            "text": "Bad question with only 1 choice",
                            "choices": [
                                {"text": "Only one", "correct": True},
                            ],
                        },
                    ],
                },
                {
                    "title": "Duplicate Title",  # Duplicate node title
                    "description": "Node 2 with no videos",
                    "videos": [],  # Empty videos list
                },
            ],
        }
        bad_path = self.tmp_path / "bad_roadmap.json"
        bad_path.write_text(json.dumps(bad_roadmap), encoding="utf-8")

        with self.assertRaises(CommandError) as ctx:
            call_command("import_roadmap", str(bad_path))

        msg = str(ctx.exception)
        self.assertIn("position 99 does not exist", msg)
        self.assertIn("position 4 (vid_004_noembed) is non-embeddable", msg)
        self.assertIn("exactly 1 correct choice", msg)
        self.assertIn("at least 2 choices", msg)
        self.assertIn("Duplicate node title", msg)
        self.assertIn("at least 1 video", msg)
        self.assertEqual(Roadmap.objects.count(), 0)

    def test_allow_non_embeddable_flag_imports_with_false_flag(self):
        self.roadmap_data["nodes"][0]["videos"] = [1, 4]
        self.roadmap_path.write_text(json.dumps(self.roadmap_data), encoding="utf-8")

        with self.assertRaises(CommandError):
            call_command("import_roadmap", str(self.roadmap_path))

        call_command(
            "import_roadmap",
            str(self.roadmap_path),
            "--allow-non-embeddable",
        )
        v4 = Video.objects.get(youtube_id="vid_004_noembed")
        self.assertFalse(v4.is_embeddable)

    def test_node_reorder_without_unique_constraint_violation(self):
        call_command("import_roadmap", str(self.roadmap_path))
        n_vars = Node.objects.get(slug="variables-and-types")
        n_funcs = Node.objects.get(slug="functions")
        self.assertEqual(n_vars.order, 1)
        self.assertEqual(n_funcs.order, 2)

        # Reverse the nodes in the JSON file and re-import
        self.roadmap_data["nodes"].reverse()
        self.roadmap_path.write_text(json.dumps(self.roadmap_data), encoding="utf-8")

        call_command("import_roadmap", str(self.roadmap_path))
        n_vars.refresh_from_db()
        n_funcs.refresh_from_db()
        self.assertEqual(n_funcs.order, 1)
        self.assertEqual(n_vars.order, 2)

    def test_quiz_with_attempts_is_not_altered(self):
        call_command("import_roadmap", str(self.roadmap_path))
        user = User.objects.create_user("student1", password="pw12345!")
        node1 = Node.objects.get(slug="variables-and-types")
        quiz1 = node1.quiz
        QuizAttempt.objects.create(user=user, quiz=quiz1, score_percent=100, passed=True)

        # Modify question text in JSON and re-import
        self.roadmap_data["nodes"][0]["quiz"][0]["text"] = "CHANGED QUESTION TEXT?"
        self.roadmap_path.write_text(json.dumps(self.roadmap_data), encoding="utf-8")

        stdout = io.StringIO()
        call_command("import_roadmap", str(self.roadmap_path), stdout=stdout)

        self.assertIn("WARNING", stdout.getvalue())
        self.assertEqual(quiz1.questions.first().text, "What is 1 + 1?")

    def test_video_with_progress_is_not_deleted(self):
        call_command("import_roadmap", str(self.roadmap_path))
        user = User.objects.create_user("student2", password="pw12345!")
        v2 = Video.objects.get(youtube_id="vid_002")
        VideoProgress.objects.create(user=user, video=v2, watched_seconds=120)

        # Remove video 2 from Node 1 in JSON and re-import
        self.roadmap_data["nodes"][0]["videos"] = [1]
        self.roadmap_path.write_text(json.dumps(self.roadmap_data), encoding="utf-8")

        stdout = io.StringIO()
        call_command("import_roadmap", str(self.roadmap_path), stdout=stdout)

        self.assertIn("WARNING", stdout.getvalue())
        self.assertTrue(Video.objects.filter(pk=v2.pk).exists())

    def test_example_json_files_import_cleanly(self):
        stdout = io.StringIO()
        call_command("import_roadmap", "data/roadmaps/example.json", stdout=stdout)
        self.assertTrue(Roadmap.objects.filter(slug="example-python-foundations").exists())
        self.assertIn("created=10, updated=0, unchanged=0", stdout.getvalue())

