# Features & Progression Engine — SkillMap (RoadmapLearn)

Every feature below is mapped directly to its implementation files and URLs.

---

## 1. Feature Map

| Feature | Implementation Files | URL Pattern / Command |
|---|---|---|
| **Authentication (Login, Logout, Signup)** | `accounts/views.py`, `accounts/urls.py`, `templates/accounts/login.html`, `templates/accounts/signup.html` | `/accounts/login/`, `/accounts/logout/`, `/accounts/signup/` |
| **Roadmap Directory, Search & Category Filter** | `roadmaps/views.py` (`roadmap_list`), `roadmaps/services.py` (`search_roadmaps`), `templates/roadmaps/roadmap_list.html` | `/roadmaps/?q=<query>&category=<slug>&page=<n>` |
| **Bookmarks & Saved Roadmaps** | `roadmaps/views.py` (`toggle_bookmark`, `saved_roadmaps`), `roadmaps/services.py`, `templates/roadmaps/_bookmark_button.html`, `templates/roadmaps/saved_roadmaps.html` | `POST /roadmaps/<slug>/bookmark/`, `GET /roadmaps/saved/` |
| **Sequential Roadmap Path** | `roadmaps/views.py` (`roadmap_detail`), `progress/services.py` (`enroll_user`, `node_statuses`, `roadmap_progress`), `templates/roadmaps/roadmap_detail.html` | `GET /roadmaps/<slug>/` |
| **Node Lesson Page (Video, Notes, Quiz Gate)** | `roadmaps/views.py` (`node_detail`), `templates/roadmaps/node_detail.html` | `GET /roadmaps/<roadmap_slug>/<node_slug>/` |
| **Anti-Cheat Video Heartbeat** | `progress/views.py` (`heartbeat`), `progress/services.py` (`record_heartbeat`, `video_check_passed`, `try_complete_node_without_quiz`) | `POST /progress/heartbeat/` |
| **Quiz Gate & Grading** | `quizzes/views.py` (`submit`), `progress/services.py` (`submit_quiz`, `complete_node`) | `POST /quizzes/<node_id>/submit/` |
| **Personal Notes (Auto-Save)** | `notes/views.py` (`save`), `notes/services.py` (`save_note`) | `POST /notes/<node_id>/save/` |
| **Student Dashboard, Streak & Badges** | `dashboard/views.py` (`home`), `dashboard/services.py` (`award_badges`, `effective_streak`, `get_dashboard_data`), `templates/dashboard/home.html` | `GET /`, `python manage.py seed_badges` |
| **Customised Nested Admin** | `roadmaps/admin.py`, `quizzes/admin.py`, `progress/admin.py`, `dashboard/admin.py`, `accounts/admin.py`, `notes/admin.py` | `/admin/` |
| **Offline Content Pipeline** | `roadmaps/management/commands/dump_playlist.py`, `roadmaps/management/commands/import_roadmap.py` | `python manage.py dump_playlist`, `python manage.py import_roadmap` |
| **Demo Fast-Forward Helper (`DEBUG` only)** | `progress/management/commands/demo_fastforward.py` | `python manage.py demo_fastforward <user> <roadmap_slug> <order>` |

---

## 2. Sequential Progression Rules (`progress/services.py`)

Constants defined in `progress/services.py`:
- `VIDEO_COMPLETION_THRESHOLD = 0.9` ($90\%$)
- `HEARTBEAT_TOLERANCE_SECONDS = 2.0`
- `MIN_PLAYBACK_RATE = 0.25`, `MAX_PLAYBACK_RATE = 2.0`
- `XP_PER_NODE_COMPLETED = 50`

1. **Enrollment (`enroll_user`)**:
   - Creates a `RoadmapEnrollment` row and one `NodeProgress` row per node in the roadmap.
   - Only the lowest-`order` node is initialized to `UNLOCKED`; all subsequent nodes start `LOCKED`.
2. **Access Control**:
   - Visiting `GET /roadmaps/<roadmap_slug>/<node_slug>/`, sending a heartbeat, or submitting a quiz for a `LOCKED` node raises `NodeLockedError` (`403 Forbidden`).
3. **Video Check (`video_check_passed`)**:
   - Sums $\min(\text{watched\_seconds}, \text{duration\_seconds})$ across all **embeddable** (`is_embeddable=True`) videos on the node.
   - Passes when total watched seconds $\ge 0.9 \times \sum \text{duration\_seconds}$ (or automatically if the node has no embeddable videos or zero total duration).
4. **Quiz Gate (`submit_quiz`)**:
   - Requires the node to be `UNLOCKED` and `video_check_passed(user, node)` to be `True`.
   - Unanswered questions count as wrong; foreign question or choice IDs raise `InvalidAnswerError` (`400 Bad Request`).
   - Every submission is recorded in `QuizAttempt(score_percent, passed)`.
   - Passes when $\text{score\_percent} \ge \text{node.quiz\_pass\_mark}$ (default $60\%$).
5. **Completion (`complete_node`)**:
   - Atomic and idempotent: transitions the current node to `COMPLETED`, unlocks the next node by `order` if `LOCKED`, awards $+50\text{ XP}$ once, updates `user.streak_days` and `user.last_active_date`, and triggers `award_badges(user)`.

---

## 3. Anti-Cheat Heartbeat Formula & Worked Numeric Example

While the embedded YouTube player state is `PLAYING`, the browser sends a heartbeat every 5 seconds to `POST /progress/heartbeat/` with `{video_id, current_time, playback_rate}`.

### Formula (`record_heartbeat`)

1. Clamp reported playback rate:
   $$r = \max(0.25, \min(2.0, \text{playback\_rate}))$$
2. On the **first heartbeat** for `(user, video)` (`last_heartbeat_at is None`):
   - `credit = 0`
   - Store `last_position = current_time`, `last_heartbeat_at = now`.
3. On **subsequent heartbeats**:
   - $\Delta t_{\text{server}} = \max(0, \text{now} - \text{last\_heartbeat\_at})$ (real wall-clock seconds elapsed on the server)
   - $\Delta p = \text{current\_time} - \text{last\_position}$ (reported forward playback delta)
   - If $\Delta p \le 0$ (rewinding or paused): $\text{credit} = 0$
   - If $\Delta p > 0$:
     $$\text{raw\_credit} = \min\left(\Delta p,\; \Delta t_{\text{server}} \times r + 2.0\right)$$
     $$\text{credit} = \lfloor \text{raw\_credit} + 0.5 \rfloor$$
4. Update cumulative watched time (never decreases, capped at `video.duration_seconds`):
   $$\text{watched\_seconds}_{\text{new}} = \max\left(\text{watched\_seconds}_{\text{old}},\; \min(\text{watched\_seconds}_{\text{old}} + \text{credit},\; \text{duration\_seconds})\right)$$

### Worked Numeric Example (100-second video)

| Step | Event | Server Elapsed ($\Delta t_{\text{server}}$) | Client `current_time` | Rate ($r$) | $\Delta p$ | Max Allowed ($\Delta t_{\text{server}} \cdot r + 2.0$) | Credited Seconds | Cumulative `watched_seconds` |
|---|---|---|---|---|---|---|---|---|
| **1** | Player starts at `0.0s` | — (first beat) | `0.0` | `1.0` | — | — | `0s` | `0s` |
| **2** | Normal playback for `5s` | `5.0s` | `5.0` | `1.0` | `5.0s` | $5.0 \times 1.0 + 2.0 = 7.0\text{s}$ | $\min(5.0, 7.0) = \mathbf{5\text{s}}$ | `5s` |
| **3** | **Student seeks forward to `95.0s` after `1s` real time** | `1.0s` | `95.0` | `1.0` | `90.0s` | $1.0 \times 1.0 + 2.0 = 3.0\text{s}$ | $\min(90.0, 3.0) = \mathbf{3\text{s}}$ | `8s` *(seek defeated; `last_position` becomes `95.0`)* |
| **4** | Student rewinds back to `5.0s` after `2s` | `2.0s` | `5.0` | `1.0` | `-90.0s` | — ($\Delta p \le 0$) | $\mathbf{0\text{s}}$ | `8s` *(rewound to `5.0`)* |
| **5** | Watches at `1.5x` speed for `60s` real time (`5.0s` $\to$ `95.0s`) | `60.0s` | `95.0` | `1.5` | `90.0s` | $60.0 \times 1.5 + 2.0 = 92.0\text{s}$ | $\min(90.0, 92.0) = \mathbf{90\text{s}}$ | `98s` ($\ge 90\%$ of `100s` $\implies$ **`video_passed = True`**) |
