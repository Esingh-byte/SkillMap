# HTTP Endpoints — SkillMap (RoadmapLearn)

Taken directly from `roadmaplearn/urls.py`, `accounts/urls.py`, `roadmaps/urls.py`, `progress/urls.py`, `quizzes/urls.py`, `notes/urls.py`, and `dashboard/urls.py`.

| URL Pattern | URL Name | HTTP Method(s) | Auth Required | CSRF | Purpose & Response Format |
|---|---|---|---|---|---|
| `/` | `dashboard:home` | `GET` | Yes (`@login_required`) | — | Student dashboard: XP, `effective_streak`, topics completed, enrolled roadmaps with next unlocked node link, earned/locked badges, and last 8 activity events. |
| `/accounts/login/` | `accounts:login` | `GET`, `POST` | Public | Yes | Django `LoginView` (`templates/accounts/login.html`). Redirects to `dashboard:home` on success. |
| `/accounts/logout/` | `accounts:logout` | `POST` | Yes | Yes | Django `LogoutView`. Logs out the current user and redirects to `accounts:login`. |
| `/accounts/signup/` | `accounts:signup` | `GET`, `POST` | Public (redirects if logged in) | Yes | Creates a new `accounts.User` via `SignupForm`, logs them in, and redirects to `dashboard:home`. |
| `/roadmaps/` | `roadmaps:list` | `GET` | Public | — | Published roadmaps list with `?q=` search (title, description, category name, node titles), `?category=<slug>` filter, and 12-per-page pagination (`?page=`). |
| `/roadmaps/saved/` | `roadmaps:saved` | `GET` | Yes (`@login_required`) | — | Displays the logged-in user's bookmarked published roadmaps (with an empty state). |
| `/roadmaps/<slug:slug>/` | `roadmaps:detail` | `GET` | Yes (`@login_required`) | — | Auto-enrolls the user (`enroll_user`), displays the segmented progress bar and vertical topic path (`COMPLETED`, `UNLOCKED`, `LOCKED`). `404` if unpublished. |
| `/roadmaps/<slug:slug>/bookmark/` | `roadmaps:bookmark` | `POST` | Yes (`@login_required`) | Yes | Toggles `RoadmapBookmark` on a published roadmap (`404` if unpublished, `405` on `GET`). Returns `_bookmark_button.html` partial for HTMX (`HX-Request: true`) or redirects back with a Django message. |
| `/roadmaps/<slug:roadmap_slug>/<slug:node_slug>/` | `roadmaps:node_detail` | `GET` | Yes (`@login_required`) | — | Node lesson page: embedded YouTube player(s), watch progress bar with 90% tick mark, quiz gate, syllabus sidebar, and personal notes. Returns `403` if not enrolled or `LOCKED`. |
| `/progress/heartbeat/` | `progress:heartbeat` | `POST` | Yes (`@login_required`) | Yes | Anti-cheat video heartbeat (`{video_id, current_time, playback_rate}`). Returns JSON `{status: "ok", watched_seconds, duration_seconds, video_passed, node_completed}`. Errors: `400` bad input/non-embeddable, `403` not enrolled/locked, `404` unknown video, `405` on `GET`. |
| `/quizzes/<int:node_id>/submit/` | `quizzes:submit` | `POST` | Yes (`@login_required`) | Yes | Grades quiz submission (`{answers: {question_id: choice_id}}`). Returns JSON `{passed, score_percent, node_completed, xp_awarded}`. Errors: `400` invalid answers, `403` locked node or video check not passed, `404` unknown node, `405` on `GET`. |
| `/notes/<int:node_id>/save/` | `notes:save` | `POST` | Yes (`@login_required`) | Yes | Upserts the user's `Note` for `node_id` (accepts JSON `{content}` or form-encoded `content`). Returns JSON `{status: "saved", updated_at}`. Errors: `400` non-string/missing content, `404` unknown node, `405` on `GET`. |
| `/admin/` | `admin:index` | `GET`, `POST` | Staff / Superuser | Yes | Customised Django Admin (`django-nested-admin` for `Node` → `Video` and `Quiz` → `Question` → `Choice`; read-only admin for `NodeProgress`, `VideoProgress`, `RoadmapEnrollment`, `QuizAttempt`, `UserBadge`). |
