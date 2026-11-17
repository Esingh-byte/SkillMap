# Testing Guide — SkillMap (RoadmapLearn)

All business logic, management commands, views, and security rules are covered by automated Django tests.

---

## 1. Running the Test Suite

Always invoke Python via the project's `.venv`:

```powershell
# Run the full test suite (currently 122 tests)
.\.venv\Scripts\python.exe manage.py test

# Run Django system checks
.\.venv\Scripts\python.exe manage.py check

# Run a single app or module
.\.venv\Scripts\python.exe manage.py test progress
.\.venv\Scripts\python.exe manage.py test roadmaps.tests.test_content_pipeline
.\.venv\Scripts\python.exe manage.py test roadmaps.tests.test_bookmarks_and_search
.\.venv\Scripts\python.exe manage.py test dashboard
```

---

## 2. Test Count & Coverage Breakdown (122 Tests Total)

| Test Module | Tests | What is Covered |
|---|---|---|
| `progress/tests/test_services.py` | 30 | `enroll_user` idempotency and initial unlock state; `record_heartbeat` anti-cheat credit math, forward-seek clamping, rewind zero credit, playback rate clamping (`[0.25, 2.0]`), duration cap, non-embeddable rejection; `video_check_passed` threshold ($90\%$); `submit_quiz` grading, foreign question/choice rejection; `complete_node` sequential unlock, single XP award (`+50 XP`), and daily streak transitions. |
| `progress/tests/test_views.py` | 10 | `POST /progress/heartbeat/`: login requirement, `405` on `GET`, `403` when not enrolled or node `LOCKED`, `400` on non-embeddable video or malformed payload, `404` on unknown video, watch credit accumulation, seek-forward clamping, auto-completion of no-quiz nodes. |
| `progress/tests/test_security_and_demo.py` | 13 | Cross-endpoint security (`heartbeat`, `quizzes:submit`, `notes:save`, `roadmaps:bookmark`, `roadmaps:detail`): anonymous redirect, `405` on `GET`, CSRF enforcement (`Client(enforce_csrf_checks=True)`), User A isolation from User B's progress/notes/bookmarks, `400` on `NaN`/`Infinity`/`-Infinity`/booleans/64-bit integer overflow; `404.html` and context-processor-free `500.html` rendering; `SECRET_KEY` check when `DEBUG=False`; `demo_fastforward` command (`DEBUG` guard, sequential completion). |
| `quizzes/tests/test_views.py` | 11 | `POST /quizzes/<node_id>/submit/` (login redirect, `403` before video check or on `LOCKED` node, `400` on invalid answers, fail vs pass unlocking next node, idempotent XP on retake) and `POST /notes/<node_id>/save/` (JSON and form-data upsert, `400` on bad content, `404` on unknown node). |
| `roadmaps/tests/test_views.py` | 10 | Public `roadmap_list` hiding drafts, category filter, `roadmap_detail` login requirement and auto-enrollment, `404` on unpublished roadmap, `node_detail` `403` when not enrolled or `LOCKED`, `accounts` signup/login/logout flows. |
| `roadmaps/tests/test_admin_smoke.py` | 8 | Admin changelist, add, and change views for `Category`, `Roadmap`, `Node` (nested inlines), `Video`, `Quiz`, `NodeProgress` (read-only), and `seed_demo` command idempotency. |
| `roadmaps/tests/test_content_pipeline.py` | 15 | ISO 8601 duration parser (`PT1H2M3S`, `PT45S`, `P0D`, invalid inputs); `dump_playlist` across 2 pages, skipping private/deleted videos while preserving 1-based positions, API key scrubbing on HTTP 403/404/runtime errors; `import_roadmap` `--dry-run`, idempotency, all-at-once validation errors, node reorder without unique constraint violation, preserving quizzes with attempts and videos with `VideoProgress`. |
| `roadmaps/tests/test_bookmarks_and_search.py` | 10 | Bookmark toggle (`POST /roadmaps/<slug>/bookmark/`) via HTMX partial and non-JS redirect, anonymous redirect, `405` on `GET`, `404` on unpublished roadmap; `/roadmaps/saved/` user isolation and empty state; `search_roadmaps` by title, description, category name, and node title, title-match ranking priority, no duplicates across matching nodes, combined category filter, and 12-item pagination preserving `q` and `category`. |
| `dashboard/tests.py` | 15 | `seed_badges` idempotency; `effective_streak` (today, yesterday, stale without DB writes, `None`); all 6 badge rules (`first_step`, `on_a_roll`, `week_warrior`, `quiz_ace`, `roadmap_finisher`, `note_taker`), automatic badge hooks in `complete_node` and `submit_quiz`; dashboard view auth redirect, empty state, and next unlocked node link target. |
