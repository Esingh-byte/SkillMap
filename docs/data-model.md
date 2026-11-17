# Data Model — SkillMap (RoadmapLearn)

All 12 models across the 6 local Django apps (`accounts`, `roadmaps`, `progress`, `quizzes`, `notes`, `dashboard`) are shown below, generated directly from each app's `models.py`.

---

## 1. Entity-Relationship Diagram

```mermaid
erDiagram
    USER ||--o{ ROADMAP_BOOKMARK : "bookmarks"
    USER ||--o{ ROADMAP_ENROLLMENT : "enrolls in"
    USER ||--o{ NODE_PROGRESS : "tracks"
    USER ||--o{ VIDEO_PROGRESS : "watches"
    USER ||--o{ QUIZ_ATTEMPT : "attempts"
    USER ||--o{ NOTE : "writes"
    USER ||--o{ USER_BADGE : "earns"

    CATEGORY ||--o{ ROADMAP : "categorizes"
    ROADMAP ||--o{ NODE : "contains"
    ROADMAP ||--o{ ROADMAP_BOOKMARK : "bookmarked via"
    ROADMAP ||--o{ ROADMAP_ENROLLMENT : "enrolled via"

    NODE ||--o{ VIDEO : "has"
    NODE ||--o{ NODE_PROGRESS : "progresses via"
    NODE ||--o| QUIZ : "gated by"
    NODE ||--o{ NOTE : "annotated by"

    VIDEO ||--o{ VIDEO_PROGRESS : "measured by"

    QUIZ ||--o{ QUESTION : "has"
    QUIZ ||--o{ QUIZ_ATTEMPT : "recorded in"
    QUESTION ||--o{ CHOICE : "offers"

    BADGE ||--o{ USER_BADGE : "awarded via"

    USER {
        bigint id PK
        string username UK
        string email
        string password
        string first_name
        string last_name
        boolean is_staff
        boolean is_active
        boolean is_superuser
        datetime date_joined
        datetime last_login
        int xp "default 0"
        int streak_days "default 0"
        date last_active_date "nullable"
    }

    CATEGORY {
        bigint id PK
        string name UK "max 100"
        string slug UK "max 100"
    }

    ROADMAP {
        bigint id PK
        string title "max 200"
        string slug UK "max 200"
        text description "blank"
        bigint category_id FK "nullable, SET_NULL"
        string thumbnail "max 255, blank"
        boolean is_published "default False"
        string source_attribution "max 255, blank"
        datetime created_at
        datetime updated_at
    }

    ROADMAP_BOOKMARK {
        bigint id PK
        bigint user_id FK
        bigint roadmap_id FK
        datetime created_at
    }

    NODE {
        bigint id PK
        bigint roadmap_id FK
        string title "max 200"
        string slug "max 200"
        text description "blank"
        smallint order "default 0"
        smallint quiz_pass_mark "default 60"
    }

    VIDEO {
        bigint id PK
        bigint node_id FK
        string youtube_id "max 20"
        string title "max 300"
        string channel_name "max 200, blank"
        int duration_seconds "default 0"
        smallint order "default 0"
        boolean is_embeddable "default True"
        datetime created_at
    }

    ROADMAP_ENROLLMENT {
        bigint id PK
        bigint user_id FK
        bigint roadmap_id FK
        datetime enrolled_at
    }

    NODE_PROGRESS {
        bigint id PK
        bigint user_id FK
        bigint node_id FK
        string status "LOCKED | UNLOCKED | COMPLETED"
        datetime unlocked_at "nullable"
        datetime completed_at "nullable"
    }

    VIDEO_PROGRESS {
        bigint id PK
        bigint user_id FK
        bigint video_id FK
        int watched_seconds "default 0"
        float last_position "default 0.0"
        datetime last_heartbeat_at "nullable"
    }

    QUIZ {
        bigint id PK
        bigint node_id FK "OneToOne"
        string title "max 200, blank"
        datetime created_at
        datetime updated_at
    }

    QUESTION {
        bigint id PK
        bigint quiz_id FK
        text text
        smallint order "default 0"
    }

    CHOICE {
        bigint id PK
        bigint question_id FK
        string text "max 500"
        boolean is_correct "default False"
    }

    QUIZ_ATTEMPT {
        bigint id PK
        bigint user_id FK
        bigint quiz_id FK
        smallint score_percent "0-100"
        boolean passed "default False"
        datetime attempted_at
    }

    NOTE {
        bigint id PK
        bigint user_id FK
        bigint node_id FK
        text content "blank"
        datetime created_at
        datetime updated_at
    }

    BADGE {
        bigint id PK
        string name UK "max 100"
        string slug UK "max 100"
        text description "blank"
        string icon "max 100, blank"
    }

    USER_BADGE {
        bigint id PK
        bigint user_id FK
        bigint badge_id FK
        datetime awarded_at
    }
```

---

## 2. Uniqueness Constraints & Indexes

| Model | App | `unique_together` / Unique Fields | Indexes |
|---|---|---|---|
| `User` | `accounts` | `username` | `["username"]`, `["email"]` |
| `Category` | `roadmaps` | `name`, `slug` | `["slug"]` |
| `Roadmap` | `roadmaps` | `slug` | `["slug"]`, `["is_published"]`, `["category"]` |
| `RoadmapBookmark` | `roadmaps` | `("user", "roadmap")` | `["user", "roadmap"]` |
| `Node` | `roadmaps` | `("roadmap", "order")`, `("roadmap", "slug")` | `["roadmap", "order"]` |
| `Video` | `roadmaps` | `("node", "order")` | `["node", "order"]`, `["youtube_id"]` |
| `RoadmapEnrollment` | `progress` | `("user", "roadmap")` | `["user", "roadmap"]` |
| `NodeProgress` | `progress` | `("user", "node")` | `["user", "node"]`, `["user", "status"]` |
| `VideoProgress` | `progress` | `("user", "video")` | `["user", "video"]` |
| `Quiz` | `quizzes` | `node` (`OneToOneField`) | PK / OneToOne index |
| `Question` | `quizzes` | — | `["quiz", "order"]` |
| `Choice` | `quizzes` | — | `["question", "is_correct"]` |
| `QuizAttempt` | `quizzes` | — | `["user", "quiz"]`, `["user", "passed"]` |
| `Note` | `notes` | `("user", "node")` | `["user", "node"]`, `["updated_at"]` |
| `Badge` | `dashboard` | `name`, `slug` | `["slug"]` |
| `UserBadge` | `dashboard` | `("user", "badge")` | `["user", "badge"]` |
