# SkillMap (RoadmapLearn)

> A Django 6.x monolith for college students to learn career roadmaps in strict sequence. Pick a roadmap inspired by **[roadmap.sh](https://roadmap.sh)**, watch embedded YouTube tutorials, take notes, and pass each topic's quiz — the next step unlocks only after you genuinely watch at least **90%** of the videos and pass the quiz.

---

## Key Features

- **Strict Sequential Progression**: Every roadmap topic (`Node`) starts `LOCKED` except the first. Completing a topic awards `+50 XP`, updates your daily streak, and unlocks the next topic in order.
- **Server-Verified Anti-Cheat Video Tracking**: The embedded YouTube IFrame Player sends a heartbeat every 5 seconds while playing (`POST /progress/heartbeat/`). The server never trusts client totals — it credits `min(reported_forward_delta, real_elapsed_seconds * clamped_rate + 2s_tolerance)` so seeking forward grants no watch credit.
- **Quiz Gate per Topic**: Multiple-choice quizzes unlock only after the 90% video watch check passes. Correct answers are never exposed to the client.
- **Personal Lined-Paper Notes**: Per-user, per-topic notes that auto-save with an 800ms debounce (`POST /notes/<node_id>/save/`).
- **Student Dashboard & Achievement Badges**: Tracks total XP, `effective_streak`, topics completed, enrolled roadmap progress with direct "Continue" links to the next unlocked topic, 6 achievement badges (`first_step`, `on_a_roll`, `week_warrior`, `quiz_ace`, `roadmap_finisher`, `note_taker`), and a recent activity feed.
- **Bookmarks & Full-Text Search**: Save roadmaps via HTMX (`POST /roadmaps/<slug>/bookmark/`) with a non-JS fallback, view saved roadmaps at `/roadmaps/saved/`, and search roadmaps by title, description, category name, or node title with title-match ranking and pagination.
- **Customised Nested Django Admin**: Edit a `Node`, its `Video`s, and its `Quiz` → `Question` → `Choice` hierarchy on a single page via `django-nested-admin`; student progress/attempt tables are read-only for auditability.
- **Offline-Ready Content Pipeline**: `dump_playlist` fetches YouTube playlist metadata via standard-library `urllib`, and `import_roadmap` validates and imports roadmap JSON definitions offline inside a single database transaction.

---

## Documentation (`docs/`)

- [Architecture & Heartbeat Sequence Diagram](docs/architecture.md)
- [Data Model & Mermaid ER Diagram](docs/data-model.md)
- [Features, Progression Rules & Worked Anti-Cheat Math](docs/features.md)
- [HTTP Endpoints Reference](docs/endpoints.md)
- [Testing Guide (122 Automated Tests)](docs/testing.md)
- [Content Guide: Adding a Roadmap](docs/content-guide.md)
- [Screenshots Checklist](docs/screenshots/README.md)

---

## Project Structure

```text
UptoSkillsInternship/
├── manage.py
├── roadmaplearn/          # Django settings, root URLs, JSON helpers (http.py)
├── accounts/              # Custom User model (xp, streak_days, last_active_date) & auth views
├── roadmaps/              # Category, Roadmap, Node, Video, RoadmapBookmark, search & CLI pipeline
├── progress/              # RoadmapEnrollment, NodeProgress, VideoProgress, progression engine & demo_fastforward
├── quizzes/               # Quiz, Question, Choice, QuizAttempt & quiz grading endpoint
├── notes/                 # Per-user per-node Note model & auto-save endpoint
├── dashboard/             # Badge, UserBadge, badge engine (seed_badges, award_badges) & dashboard view
├── templates/             # Worksheet-styled Django templates (base, roadmaps, dashboard, accounts, 404, 500)
├── static/css/app.css     # "Printed worksheet" design system CSS variables & components
├── data/                  # Offline playlist dumps (data/playlists/) & roadmap specs (data/roadmaps/)
└── docs/                  # Architecture, ER diagram, features, endpoints, testing & content docs
```

---

## Local Setup (Windows)

> All commands use the project's `.venv` Python directly (`.\.venv\Scripts\python.exe`).

### 1. Clone the repository

```powershell
git clone https://github.com/Esingh-byte/SkillMap.git
cd UptoSkillsInternship
```

### 2. Create the virtual environment & install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set `SECRET_KEY` (and optionally `YOUTUBE_API_KEY` if dumping new playlists from YouTube). Never commit `.env`.

### 4. Apply migrations & seed data

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_badges
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py seed_production_roadmaps
```

### 5. Create a superuser (optional)

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

### 6. Run the development server

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

---

## Environment Variables

| Variable | Default (Dev) | Description |
|---|---|---|
| `SECRET_KEY` | Dev-only placeholder | Django secret key — **required when `DEBUG=False`** (raises `ImproperlyConfigured` if missing) |
| `DEBUG` | `True` | Set to `False` in production (enables secure cookies, `NOSNIFF`, `X_FRAME_OPTIONS="DENY"`, SSL redirect) |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | Comma-separated list of allowed hostnames |
| `CSRF_TRUSTED_ORIGINS` | _(empty)_ | Comma-separated list of trusted origins (e.g. `https://example.com`) |
| `SECURE_SSL_REDIRECT` | `True` (when `DEBUG=False`) | Redirect HTTP to HTTPS when `DEBUG=False` |
| `DB_ENGINE` | `django.db.backends.sqlite3` | Set to `django.db.backends.postgresql` for PostgreSQL |
| `DB_NAME` | `db.sqlite3` | Database name or SQLite file path |
| `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | _(empty)_ | PostgreSQL connection credentials |
| `YOUTUBE_API_KEY` | _(empty)_ | YouTube Data API v3 key (used only by `manage.py dump_playlist`) |

---

## Adding a Roadmap

See [docs/content-guide.md](docs/content-guide.md) and [data/README.md](data/README.md) for the full JSON schema:

```powershell
# 1. Dump a YouTube playlist to JSON (requires YOUTUBE_API_KEY)
.\.venv\Scripts\python.exe manage.py dump_playlist <playlist_id_or_url> --out data/playlists/<name>.json

# 2. Validate & preview the import plan offline
.\.venv\Scripts\python.exe manage.py import_roadmap data/roadmaps/example.json --dry-run

# 3. Import into the database
.\.venv\Scripts\python.exe manage.py import_roadmap data/roadmaps/example.json
```

---

## Running Tests & Checks

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

The test suite currently runs **122 automated tests** across progression math, views, admin smoke tests, content pipeline commands, badges/dashboard, bookmarks/search, and endpoint security.

---

## Attributions

- Roadmap topic structures are inspired by **[roadmap.sh](https://roadmap.sh)**.
- Video tutorials belong to their respective creators on YouTube — including **Krish Naik**, **CampusX**, **Love Babbar**, **freeCodeCamp.org**, **Corey Schafer**, and **Tech With Tim** — and play directly through the official YouTube IFrame Player.
