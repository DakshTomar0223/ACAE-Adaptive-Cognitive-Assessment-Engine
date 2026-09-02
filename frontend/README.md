# ACAE Frontend — Phase 6B (Quiz) + 6C (Results)

Next.js (App Router) frontend for the ACAE Flask API. Phase 6B covers the
quiz-taking flow: pick a student + topic, answer one unattempted question
at a time, get correct/incorrect feedback, repeat until the topic runs
out of questions. Phase 6C adds the results/diagnosis screen described
below.

## Requirements

- Node.js 18.18+ (Next.js 14 requirement)
- The ACAE Flask API (`backend/api.py`) running and reachable — by
  default at `http://127.0.0.1:5000`

## Setup

```
npm install
```

`.env.local` is already set to:

```
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:5000
```

Change that if your API runs somewhere else, then restart the dev server
— Next.js only reads `.env.local` at startup.

## Run

With the Flask API already running in another terminal:

```
npm run dev
```

Open http://localhost:3000.

## What it does

1. **Setup** — type a student ID and pick a topic from the dropdown
   (populated from `GET /api/topics`). "Start quiz" is disabled until
   both are filled in.
2. **Quiz** — fetches one unattempted question from `GET /api/quiz/next`
   and shows its stem and four options as buttons. The server response
   for this endpoint never includes which option is correct or its error
   category — that's by design (see `backend/api.py`), so there's nothing
   in the browser's network tab for the answer to leak from.
3. **Answer** — clicking an option records the elapsed time since the
   question was shown (`performance.now()`-based, not wall-clock), then
   `POST`s `{student_id, topic_id, question_id, option_id,
   time_taken_sec}` to `/api/quiz/answer`. The response's `is_correct`
   and `correct_option_id` drive the inline feedback (correct option
   highlighted teal, an incorrect pick highlighted coral).
4. **Next** — clicking "Next question" repeats step 2.
5. **Done** — when `/api/quiz/next` returns `question: null`, a "no more
   questions" card replaces the quiz, with a way to pick a different
   topic or student.

Network or server errors at any step show an error card with a retry
button rather than a blank screen.

## Results screen (`/results`, Phase 6C)

Reads the same student/topic diagnosis `GET /api/quiz/next` and
`POST /api/quiz/answer` feed, via `GET /api/results?student_id=&topic_id=`
— the payload `export_dashboard_data.py` builds, the same shape
`dashboard.html` (Phase 5) consumed.

1. **Setup** — student ID + topic dropdown (same data source as the quiz
   screen's setup step), with a "View results" button, plus a
   **"See a sample result"** button that's always available.
2. **Stats** — accuracy % and total attempts as headline numbers.
3. **Error breakdown** — a horizontal bar per error category from
   `chart_data`, sorted by share of wrong answers. Replaces
   `dashboard.html`'s radial SVG with a plain bar list — same data,
   simpler to scan without the kiosk/tablet constraint that shaped the
   original.
4. **Weak point diagnosis** — a status-toned callout keyed off
   `weak_point_info.status`. The four states the confidence gate can
   report are shown honestly rather than collapsed into one message:
   - `no_signal` — not enough attempts/errors yet to say anything
   - `provisional` — a leading category exists but the topic hasn't hit
     the confidence-gate attempt threshold; framed as tentative
   - `no_clear_pattern` — gate met, but errors are spread too evenly to
     name one dominant category
   - `confident` — gate met and one category clearly dominates (the
     coral callout `dashboard.html` used)
5. **Remedial pathway** — `weak_point_info.remedial_note` plus the
   `selected_questions` drill queue, shown together (only rendered when
   either is present).

### Sample data toggle

"See a sample result" `POST`s `/api/sample/generate` (reseeds the demo
DB) then fetches `GET /api/results/sample`, pinned to the demo
student/topic. The results are shown with an amber **"Sample data"**
banner and a "Switch to live results" link back to the setup form —
this is server-backed (a real API call + a `isSample` UI flag), not a
`sessionStorage`/local-state toggle the way Phase 5C's Streamlit version
was.

## Structure

```
app/
  layout.tsx              root layout — loads Fraunces/Inter/IBM Plex Mono
  globals.css              design tokens (shared with dashboard.html's palette)
  page.tsx                  the quiz screen (client component)
  page.module.css           quiz screen styles
  results/
    page.tsx                 the results screen (client component)
    results.module.css       results screen styles
lib/
  api.ts                    typed fetch() wrapper for all API endpoints in use
```

## Notes

- No data-fetching library — plain `fetch()` per the brief, wrapped once
  in `lib/api.ts` so error handling and the base URL live in one place.
- Visual language intentionally reuses the ink/parchment/amber/teal/coral
  palette and Fraunces/Inter/IBM Plex Mono type system already
  established by `dashboard.html`, so the quiz screen and results screen
  read as one product rather than two different apps.
- The results screen's status→copy mapping assumes `weak_point_info`
  always includes `status`, `dominant_category`, `share_of_errors`, and
  optionally `message`/`remedial_note`/`selected_questions` — matching
  what `export_dashboard_data.py` / `dashboard.html` already produce and
  consume. If the live `/api/results` response shape differs, adjust the
  `WeakPointInfo` type and the `switch` in `WeakPointCallout` (in
  `app/results/page.tsx`) to match.