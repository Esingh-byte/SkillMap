# Project: RoadmapLearn
A Django web app for college students. Students pick a career roadmap (based on roadmap.sh topic structure), and learn each topic through free YouTube videos embedded on our site. Progress is strictly sequential: a node stays LOCKED until the previous node is COMPLETED.

## Tech stack (do not change)
- Python 3.11+, Django 6.x (installed: 6.1.3), SQLite for dev (PostgreSQL-ready settings via env vars)
- Django templates + HTMX for interactivity, Tailwind CSS for styling (CDN is fine for now)
- No React, no separate SPA. Keep it a Django monolith.
- Django admin is a first-class feature (customised, not default).
- django-nested-admin 4.1.6 — used for Node admin: Videos + Quiz→Questions→Choices nested inlines.

## Core mechanic
A node is COMPLETED only when BOTH are true:
1. Anti-cheat video check passed: cumulative genuinely-watched time >= 90% of total video duration (sum across all videos in the node).
2. The node's quiz is passed (pass mark configurable per node, default 60%).
Then the next node (by `order`) becomes UNLOCKED.

## Anti-cheat design (important)
- Use the YouTube IFrame Player API on the client. Do NOT redirect to youtube.com.
- Client sends a heartbeat every 5 seconds while the player state is PLAYING: {video_id, current_time}.
- Server NEVER trusts the client's totals. On each heartbeat the server adds
  min(reported_forward_delta, real_elapsed_seconds_since_last_heartbeat + 2s tolerance)
  to watched_seconds. Seeking forward therefore does not add credit.
- Server stores watched_seconds, last_position, last_heartbeat_at per user per video.

## Features
1. Roadmaps list + detail page showing nodes as a vertical path (locked / unlocked / completed states)
2. Node page: embedded video(s), notes panel, then quiz once video check passed
3. Quiz gate per node (multiple choice, admin-editable)
4. Personal notes per node (per user)
5. Dashboard: progress % per roadmap, daily streak, XP, badges
6. Bookmark roadmaps + search roadmaps (title/description/category)
7. Customised Django admin: add a node with its videos and quiz on one page (inlines), search, filters
8. Management command: import_playlist <playlist_id> --roadmap <slug> using YouTube Data API v3 (store video id, title, channel, duration, embeddable flag). API key from env var YOUTUBE_API_KEY.
9. Management command: load roadmap node structure from JSON file.

## Initial roadmaps (content sources)
- Python Developer: Krish Naik's Python playlist (topics from roadmap.sh Python roadmap, only topics covered by the playlist)
- Machine Learning: CampusX or Krish Naik playlist
- Full Stack Development: Love Babbar's playlist
Attribute video creators and roadmap.sh on the site.

## Conventions
- Apps: accounts, roadmaps, progress, quizzes, notes, dashboard
- Business logic (unlock rules, anti-cheat math) lives in services.py, not in views, and has unit tests
- Small commits, one feature at a time. Run migrations and tests after each task.
- Ask before adding any new dependency.
- **Always run Python via the project's `.venv`, never the global/conda environment.**
  Use `.\.venv\Scripts\python.exe manage.py …` on Windows.

---

## Current data model

### App: accounts

#### User  (AUTH_USER_MODEL = "accounts.User", extends AbstractUser)
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| username | CharField | inherited from AbstractUser |
| email | EmailField | inherited |
| password | CharField | inherited |
| first_name | CharField | inherited |
| last_name | CharField | inherited |
| is_staff | BooleanField | inherited |
| is_active | BooleanField | inherited |
| is_superuser | BooleanField | inherited |
| date_joined | DateTimeField | inherited |
| last_login | DateTimeField | inherited |
| xp | PositiveIntegerField | default=0; total XP earned |
| streak_days | PositiveIntegerField | default=0; current daily streak |
| last_active_date | DateField | null/blank; date of last activity for streak calc |
Indexes: username, email

---

### App: roadmaps

#### Category
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| name | CharField(100) | unique |
| slug | SlugField(100) | unique |
Indexes: slug

#### Roadmap
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| title | CharField(200) | |
| slug | SlugField(200) | unique |
| description | TextField | blank |
| category | FK → Category | null/blank, SET_NULL |
| thumbnail | CharField(255) | blank; placeholder until Pillow installed |
| is_published | BooleanField | default=False |
| created_at | DateTimeField | auto_now_add |
| updated_at | DateTimeField | auto_now |
| source_attribution | CharField(255) | blank; e.g. "roadmap.sh – Python Roadmap" |
Indexes: slug, is_published, category

#### Node
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| roadmap | FK → Roadmap | CASCADE |
| title | CharField(200) | |
| slug | SlugField(200) | |
| description | TextField | blank |
| order | PositiveSmallIntegerField | default=0; position within roadmap |
| quiz_pass_mark | PositiveSmallIntegerField | default=60; % needed to pass |
unique_together: (roadmap, order), (roadmap, slug)
Indexes: (roadmap, order)

#### Video
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| node | FK → Node | CASCADE |
| youtube_id | CharField(20) | YouTube video ID (11 chars) |
| title | CharField(300) | |
| channel_name | CharField(200) | blank |
| duration_seconds | PositiveIntegerField | default=0; from YouTube API |
| order | PositiveSmallIntegerField | default=0; display order within node |
| is_embeddable | BooleanField | default=True |
| created_at | DateTimeField | auto_now_add |
unique_together: (node, order)
Indexes: (node, order), youtube_id

#### RoadmapBookmark
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| user | FK → accounts.User | CASCADE |
| roadmap | FK → Roadmap | CASCADE |
| created_at | DateTimeField | auto_now_add |
unique_together: (user, roadmap)
Indexes: (user, roadmap)

---

### App: progress

#### NodeProgress
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| user | FK → accounts.User | CASCADE |
| node | FK → roadmaps.Node | CASCADE |
| status | CharField(10) | choices: LOCKED / UNLOCKED / COMPLETED |
| unlocked_at | DateTimeField | null/blank |
| completed_at | DateTimeField | null/blank |
unique_together: (user, node)
Indexes: (user, node), (user, status)
Admin: READ-ONLY (view + delete only for superusers, no add/change)

#### VideoProgress
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| user | FK → accounts.User | CASCADE |
| video | FK → roadmaps.Video | CASCADE |
| watched_seconds | PositiveIntegerField | default=0; server-verified cumulative seconds |
| last_position | FloatField | default=0.0; last client-reported position |
| last_heartbeat_at | DateTimeField | null/blank; timestamp of last heartbeat |
unique_together: (user, video)
Indexes: (user, video)
Admin: READ-ONLY

#### RoadmapEnrollment
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| user | FK → accounts.User | CASCADE |
| roadmap | FK → roadmaps.Roadmap | CASCADE |
| enrolled_at | DateTimeField | auto_now_add |
unique_together: (user, roadmap)
Indexes: (user, roadmap)
Admin: READ-ONLY

---

### App: quizzes

#### Quiz
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| node | OneToOneField → roadmaps.Node | CASCADE |
| title | CharField(200) | blank |
| created_at | DateTimeField | auto_now_add |
| updated_at | DateTimeField | auto_now |

#### Question
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| quiz | FK → Quiz | CASCADE |
| text | TextField | question body |
| order | PositiveSmallIntegerField | default=0 |
Indexes: (quiz, order)
Validation: must have ≥ 2 choices and exactly 1 correct choice (formset clean)

#### Choice
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| question | FK → Question | CASCADE |
| text | CharField(500) | |
| is_correct | BooleanField | default=False |
Indexes: (question, is_correct)

#### QuizAttempt
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| user | FK → accounts.User | CASCADE |
| quiz | FK → Quiz | CASCADE |
| score_percent | PositiveSmallIntegerField | 0–100 |
| passed | BooleanField | default=False |
| attempted_at | DateTimeField | auto_now_add |
Indexes: (user, quiz), (user, passed)
Admin: READ-ONLY

---

### App: notes

#### Note
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| user | FK → accounts.User | CASCADE |
| node | FK → roadmaps.Node | CASCADE |
| content | TextField | blank |
| created_at | DateTimeField | auto_now_add |
| updated_at | DateTimeField | auto_now |
unique_together: (user, node)
Indexes: (user, node), updated_at

---

### App: dashboard

#### Badge
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| name | CharField(100) | unique |
| slug | SlugField(100) | unique |
| description | TextField | blank |
| icon | CharField(100) | blank; CSS class or emoji |
Indexes: slug

#### UserBadge
| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| user | FK → accounts.User | CASCADE |
| badge | FK → Badge | CASCADE |
| awarded_at | DateTimeField | auto_now_add |
unique_together: (user, badge)
Indexes: (user, badge)
Admin: READ-ONLY

---

## Agent rules (tool-independent)
- Django 6.1 monolith; Django templates + HTMX + Tailwind; no React; SQLite for dev.
- Read PROJECT_CONTEXT.md before each task; update it when models or rules change.
- Use existing names exactly (`Video`, not Resource; `Node.quiz_pass_mark`; User `xp` / `streak_days` / `last_active_date`). Never rename without asking.
- Business logic lives in `services.py` with unit tests, never in views.
- Django 6: `format_html()` needs at least one argument; use `mark_safe` for static HTML.
- Secrets only via `.env`; never commit `.env`, `db.sqlite3`, `.venv`.
- Ask before adding any dependency. If a model change or migration is needed, stop and ask first.
- Small steps; run tests and `manage.py check` after each task; commit; automatically push clean commits to `origin main` (only essential code, tests, and config; never temporary/scratch files).

## Progression rules
Implemented in `progress/services.py` (tests in `progress/tests/test_services.py`). Constants: `VIDEO_COMPLETION_THRESHOLD=0.9`, `HEARTBEAT_TOLERANCE_SECONDS=2.0`, `MAX_PLAYBACK_RATE=2.0`, `MIN_PLAYBACK_RATE=0.25`, `XP_PER_NODE_COMPLETED=50`.
- `NodeProgress.status` defaults to LOCKED. `enroll_user` UNLOCKS only the lowest-`order` node; `Node` itself has no status field.
- Heartbeat is rejected for non-enrolled users (`NotEnrolledError`), LOCKED nodes (`NodeLockedError`) and non-embeddable videos (`VideoNotEmbeddableError`).
- `playback_rate` is clamped to [0.25, 2.0].
- Credit: first heartbeat credits 0. Later: `delta = current_time - last_position`; if `delta <= 0` credit 0, else `credit = min(delta, elapsed * rate + 2.0)`. `watched_seconds` (integer column, so credit is rounded to whole seconds) never decreases and never exceeds `Video.duration_seconds`.
- Video check: sum of `min(watched, duration)` over EMBEDDABLE videos >= 0.9 * sum of their durations. A node with no embeddable videos (or zero total duration) passes automatically.
- Quiz: needs an unlocked node and a passed video check; unanswered = wrong; pass when score >= `Node.quiz_pass_mark`; every attempt is stored in `QuizAttempt`. Foreign questions/choices raise `InvalidAnswerError`.
- `complete_node` is atomic and idempotent: sets COMPLETED, unlocks the next higher `order` only if LOCKED, awards XP once, updates streak.
- Nodes without a quiz (or with no questions) complete via `try_complete_node_without_quiz` once the video check passes.
- Streak: same day no change; yesterday +1; otherwise reset to 1.

## Project status

### Done
- 16 models in 6 apps, with `__str__` and indexes
- Customised admin (django-nested-admin; read-only admin for progress/attempt models)
- `seed_demo` command
- Admin Video list crash fixed; admin smoke tests (`roadmaps/tests/test_admin_smoke.py`)
- Progression engine (`progress/services.py`) with unit tests
- Venv, `.gitignore`, `.env.example`, git + GitHub remote

### Pending
- Views and UI
- YouTube playlist importer
- Dashboard
- Bookmarks and search
- Documentation
