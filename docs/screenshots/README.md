# Screenshots Checklist for Project Report

Capture the following pages from your local server (`.\.venv\Scripts\python.exe manage.py runserver`) and save them in this directory (`docs/screenshots/`) for inclusion in the internship report or presentation:

1. **`01-roadmap-list-and-search.png` — Roadmaps Directory (`/roadmaps/`)**
   - Shows the "Learn it in order." worksheet hero, search input (`?q=`), category filter pills, roadmap cards with step counts and "Save" / "Saved" bookmark buttons, and footer attribution.
2. **`02-roadmap-vertical-path.png` — Sequential Roadmap Path (`/roadmaps/<slug>/`)**
   - Shows the header card with the segmented `.sk-blocks` progress bar (`completed / total topics · %`), source attribution, and the vertical path with `COMPLETED` (forest green + check icon), `UNLOCKED` (marigold + "Up next" badge + "Continue" button), and `LOCKED` (hatched marker + padlock icon + dashed card) states.
3. **`03-node-lesson-locked-quiz.png` — Node Lesson Page Before Video Check (`/roadmaps/<roadmap_slug>/<node_slug>/`)**
   - Shows the 16:9 YouTube player with hard ink shadow, creator attribution, watch progress bar with the `90% needed` tick mark, hatched locked quiz panel, syllabus sidebar, and lined-paper Personal Notes card.
4. **`04-node-lesson-quiz-unlocked-and-passed.png` — Node Lesson Page With Unlocked Quiz & Score Feedback**
   - Shows the watch bar at $100\%$, the unlocked multiple-choice quiz form, the score/XP readout after submitting (`Passed - score 100% - node completed, +50 XP`), and the "Next topic" button.
5. **`05-student-dashboard.png` — Student Dashboard (`/`)**
   - Shows the top stat cards (`XP`, `Daily streak`, `Topics completed`), "Continue learning" roadmap cards pointing to the next unlocked topic, earned vs locked hatched badges (`First Step`, `Quiz Ace`, `On a Roll`, etc.), and the Recent Activity feed.
6. **`06-saved-roadmaps.png` — Saved Roadmaps Page (`/roadmaps/saved/`)**
   - Shows the user's bookmarked roadmaps (or the empty state before saving a roadmap).
7. **`07-custom-nested-admin.png` — Customised Django Admin (`/admin/roadmaps/node/<id>/change/`)**
   - Shows editing a `Node` with its inline `Video` rows and nested `Quiz` → `Question` → `Choice` inlines on a single page, plus read-only `NodeProgress` / `VideoProgress` audit views.

> **Tip for capturing step 4 & 5 quickly in development:**
> Use the `DEBUG`-only helper command to fast-forward a demo user to any node order:
> ```powershell
> .\.venv\Scripts\python.exe manage.py demo_fastforward <username> python-developer 3
> ```
