# RoadmapLearn

> A Django web app for college students. Pick a career roadmap, learn each topic through free YouTube videos, and unlock the next node only after genuinely watching the video **and** passing the quiz.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, Django 6.x |
| Database | SQLite (dev) · PostgreSQL-ready via env vars |
| Frontend | Django templates + HTMX + Tailwind CSS (CDN) |
| Admin | Django admin (customised with inlines & filters) |

---

## Project Layout

```
UptoSkillsInternship/
├── manage.py
├── roadmaplearn/          # Django project package
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── accounts/              # Custom User model (XP, streak)
│   ├── models.py
│   ├── admin.py
│   ├── services.py
│   ├── urls.py
│   └── migrations/
├── roadmaps/              # Roadmap, Node, Video, Category, Bookmark
│   ├── models.py
│   ├── admin.py
│   ├── services.py
│   ├── urls.py
│   └── migrations/
├── progress/              # NodeProgress, VideoProgress, Enrollment
│   ├── models.py          # Anti-cheat heartbeat logic lives in services.py
│   ├── admin.py
│   ├── services.py
│   ├── urls.py
│   └── migrations/
├── quizzes/               # Quiz, Question, Choice, QuizAttempt
│   ├── models.py
│   ├── admin.py
│   ├── services.py
│   ├── urls.py
│   └── migrations/
├── notes/                 # Personal notes per user per node
│   ├── models.py
│   ├── admin.py
│   ├── services.py
│   ├── urls.py
│   └── migrations/
└── dashboard/             # Badge, UserBadge; XP & streak display
    ├── models.py
    ├── admin.py
    ├── services.py
    ├── urls.py
    └── migrations/
```

---

## Local Setup (Windows)

> All commands use the venv Python directly — no activation or execution-policy change needed.

### 1 · Clone the repository

```powershell
git clone <repo-url>
cd UptoSkillsInternship
```

### 2 · Create the virtual environment

```powershell
python -m venv .venv
```

Verify it was created:

```powershell
.\.venv\Scripts\python.exe --version   # should print Python 3.x.x
```

### 3 · Install dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4 · Configure environment variables

```powershell
Copy-Item .env.example .env
```

Open `.env` in any editor and set at minimum:

```
SECRET_KEY=<a-long-random-string>
DEBUG=True
```

> **Never commit `.env` to version control.** It is listed in `.gitignore`.

### 5 · Apply migrations

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

### 6 · Create a superuser

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

You will be prompted for username, email, and password.

### 7 · (Optional) Load demo data

```powershell
.\.venv\Scripts\python.exe manage.py seed_demo
```

Creates one published roadmap with 3 nodes, videos, and quizzes.

### 8 · Run the development server

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Open **http://127.0.0.1:8000/admin/** and log in with your superuser credentials.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | insecure placeholder | Django secret key – **must be set in production** |
| `DEBUG` | `True` | Set to `False` in production |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | Comma-separated list |
| `DB_ENGINE` | `django.db.backends.sqlite3` | Switch to `django.db.backends.postgresql` for Postgres |
| `DB_NAME` | `db.sqlite3` | Database name / path |
| `DB_USER` | _(empty)_ | Database user |
| `DB_PASSWORD` | _(empty)_ | Database password |
| `DB_HOST` | _(empty)_ | Database host |
| `DB_PORT` | _(empty)_ | Database port |
| `YOUTUBE_API_KEY` | _(empty)_ | YouTube Data API v3 key (for `import_playlist` command) |

---

## Admin Highlights

| App | Registered Models | Inlines |
|---|---|---|
| accounts | User | — |
| roadmaps | Category, Roadmap, Node, Video, RoadmapBookmark | Roadmap → Nodes · Node → Videos |
| progress | NodeProgress, VideoProgress, RoadmapEnrollment | — |
| quizzes | Quiz, Question, Choice, QuizAttempt | Quiz → Questions · Question → Choices |
| notes | Note | — |
| dashboard | Badge, UserBadge | — |

---

## Core Mechanic – Node Unlock

A node is **COMPLETED** only when **both** conditions are true:

1. **Video check passed** – cumulative *genuinely-watched* seconds ≥ 90 % of total video duration.
2. **Quiz passed** – score ≥ `node.quiz_pass_mark` (default 60 %).

The next node (by `order`) then becomes **UNLOCKED**.

### Anti-cheat (heartbeat)

- The YouTube IFrame Player API sends a heartbeat every 5 s while `state = PLAYING`: `{resource_id, current_time}`.
- The server **never** trusts the client's total. On each heartbeat it adds:

  ```
  min(reported_forward_delta, real_elapsed_since_last_heartbeat + 2s_tolerance)
  ```

  to `VideoProgress.watched_seconds`. Seeking forward gives no credit.

---

## Attributions

- Roadmap structures inspired by **[roadmap.sh](https://roadmap.sh)**
- Video content sourced from: **Krish Naik** (Python), **CampusX / Krish Naik** (ML), **Love Babbar** (Full Stack)

---

## Running Tests

```bash
python manage.py test
```

Business-logic unit tests live in each app's `tests.py`; services reside in `services.py`.
