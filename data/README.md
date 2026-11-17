# Content Pipeline (`data/`)

This directory holds two-stage JSON artifacts used to build and update roadmaps:

1. **`data/playlists/<name>.json`** — Offline dumps of YouTube playlists fetched via `dump_playlist`.
2. **`data/roadmaps/<name>.json`** — Curated roadmap definitions mapping topic nodes and quizzes to playlist positions, imported offline via `import_roadmap`.

---

## 1. Dumping a YouTube Playlist (`dump_playlist`)

`dump_playlist` queries the YouTube Data API v3 (`playlistItems.list` + `videos.list`) using `YOUTUBE_API_KEY` from your environment / `.env` and writes a normalized JSON file.

```powershell
.\.venv\Scripts\python.exe manage.py dump_playlist PLu0W_9lII9agwh1XjRt242xIpHhPT2llg --out data/playlists/python.json
```

You can pass either a bare playlist ID or a full URL containing `list=`:

```powershell
.\.venv\Scripts\python.exe manage.py dump_playlist "https://www.youtube.com/playlist?list=PLu0W_9lII9agwh1XjRt242xIpHhPT2llg" --out data/playlists/python.json
```

### Playlist JSON Format (`data/playlists/<name>.json`)

```json
{
  "playlist_id": "PLexampleFictionalPlaylist001",
  "title": "Fictional Python Crash Course",
  "channel": "Example Code Academy",
  "fetched_at": "2026-11-17T08:00:00+00:00",
  "videos": [
    {
      "position": 1,
      "video_id": "exVid000001",
      "title": "1. Installing Python and Running Your First Script",
      "channel": "Example Code Academy",
      "duration_seconds": 420,
      "embeddable": true
    }
  ]
}
```

- Private or deleted videos are automatically skipped and listed in the console summary, while preserving the original 1-based playlist `position` of every remaining video.
- `YOUTUBE_API_KEY` is never logged or written to disk.

---

## 2. Importing a Roadmap Offline (`import_roadmap`)

`import_roadmap` validates a roadmap JSON file against its local playlist dump and writes `Category`, `Roadmap`, `Node`, `Video`, `Quiz`, `Question`, and `Choice` records inside a single database transaction. **No API key or network connection is needed.**

### Preview with `--dry-run`

```powershell
.\.venv\Scripts\python.exe manage.py import_roadmap data/roadmaps/example.json --dry-run
```

### Run the Import

```powershell
.\.venv\Scripts\python.exe manage.py import_roadmap data/roadmaps/example.json
```

If a playlist contains videos with `"embeddable": false` and you intentionally want to import them (stored with `is_embeddable=False`):

```powershell
.\.venv\Scripts\python.exe manage.py import_roadmap data/roadmaps/example.json --allow-non-embeddable
```

### Roadmap JSON Format (`data/roadmaps/<name>.json`)

```json
{
  "slug": "example-python-foundations",
  "title": "Example Python Foundations",
  "description": "A concise two-step introductory Python roadmap built from the offline example playlist.",
  "category": "Programming",
  "source_attribution": "roadmap.sh – Python Roadmap",
  "is_published": false,
  "playlist": "data/playlists/example.json",
  "nodes": [
    {
      "title": "Getting Started & Variables",
      "description": "Set up your Python environment and learn core primitive types.",
      "section_label": "Fundamentals",
      "quiz_pass_mark": 60,
      "videos": [1, 2],
      "quiz": [
        {
          "text": "Which function displays output in the terminal in Python?",
          "explanation": "print() writes objects to standard output.",
          "choices": [
            {"text": "echo()", "correct": false},
            {"text": "print()", "correct": true},
            {"text": "console.log()", "correct": false}
          ]
        }
      ]
    }
  ]
}
```

### Safety & Idempotency Guarantees
- **All-at-once validation**: Missing keys, unknown playlist positions, non-embeddable videos (without `--allow-non-embeddable`), nodes with no videos, duplicate node titles, and questions violating the `>= 2 choices` / `exactly 1 correct` rule are all reported together before any database write.
- **Safe reordering**: Node and video `order` updates use temporary high orders inside the transaction so `(roadmap, order)` and `(node, order)` uniqueness constraints are never violated.
- **Student progress protection**:
  - Videos that already have `VideoProgress` rows are never deleted.
  - Quizzes that already have `QuizAttempt` rows are never overwritten.
- **Idempotent**: Running `import_roadmap` a second time on an unchanged file creates `0` new records.
