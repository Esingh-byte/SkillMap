# Content Guide: Adding a Roadmap — SkillMap (RoadmapLearn)

Roadmaps are added or updated using a two-step offline-friendly pipeline with zero third-party HTTP dependencies:

1. **`dump_playlist`** fetches a YouTube playlist once using `YOUTUBE_API_KEY` and writes a normalized JSON file under `data/playlists/`.
2. **`import_roadmap`** validates and imports a roadmap definition from `data/roadmaps/` against that local playlist dump inside a single database transaction (no API key or internet connection required).

---

## Step 1: Dump a YouTube Playlist (`dump_playlist`)

Set `YOUTUBE_API_KEY` in your `.env` file (or environment), then run:

```powershell
.\.venv\Scripts\python.exe manage.py dump_playlist PLu0W_9lII9agwh1XjRt242xIpHhPT2llg --out data/playlists/python.json
```

You can also pass a full YouTube playlist URL containing `list=`:

```powershell
.\.venv\Scripts\python.exe manage.py dump_playlist "https://www.youtube.com/playlist?list=PLu0W_9lII9agwh1XjRt242xIpHhPT2llg" --out data/playlists/python.json
```

### What `dump_playlist` Does
- Calls `playlistItems.list` (`part=snippet,contentDetails`, `maxResults=50`, following `nextPageToken`) and then `videos.list` (`part=contentDetails,status,snippet`) in chunks of 50 video IDs.
- Skips private or deleted videos and lists their positions in the console summary while preserving the original 1-based playlist `position` of every remaining video.
- Converts ISO 8601 durations (`PT1H2M3S`, `PT45S`, `P0D`) into `duration_seconds`.
- Never prints or logs `YOUTUBE_API_KEY`.

---

## Step 2: Author the Roadmap JSON (`data/roadmaps/<name>.json`)

Create a JSON file mapping sequential topic nodes and multiple-choice quizzes to 1-based `"videos"` positions from the playlist dump. See `data/roadmaps/example.json` for a working example:

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

### Validation Rules Enforced Before Writing
- All required top-level keys (`slug`, `title`, `description`, `category`, `source_attribution`, `playlist`, `nodes`) must be present.
- Node titles must be unique within the file.
- Every node must reference at least 1 video position, and every position must exist in the playlist file.
- Every referenced video must have `"embeddable": true` unless `--allow-non-embeddable` is passed.
- Every quiz question must have at least 2 choices and **exactly 1** choice with `"correct": true`.

---

## Step 3: Preview & Import (`import_roadmap`)

Preview the import plan without writing to the database:

```powershell
.\.venv\Scripts\python.exe manage.py import_roadmap data/roadmaps/example.json --dry-run
```

Run the import:

```powershell
.\.venv\Scripts\python.exe manage.py import_roadmap data/roadmaps/example.json
```

### Re-running & Updating Safely
- `import_roadmap` is **idempotent**: running it twice on an unchanged file creates and updates `0` records.
- Reordering nodes or videos in the JSON file is handled safely inside `transaction.atomic()` using temporary high `order` values.
- Videos with existing student `VideoProgress` are never deleted, and quizzes with existing `QuizAttempt` records are never overwritten.
