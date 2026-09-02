# ACAE — Adaptive Cognitive Assessment Engine

ACAE is a JEE/NEET practice-question tool that doesn't just mark answers
right or wrong — it figures out *why* a student keeps getting a topic
wrong (careless mistake? misread the diagram? misunderstood the concept?
ran out of time?) and then gives them practice aimed at that specific
weak point, instead of generic "try again" practice.

It does this with **distractor-mapped multiple-choice questions**: every
wrong option in a question is written to represent one specific kind of
reasoning mistake, not just a random wrong number. So which wrong answer a
student picks is itself diagnostic data — the system doesn't need to watch
them work, it can tell a lot just from *which* wrong option they chose,
repeated across enough questions in a topic.

For the full architecture, the 9-category error taxonomy, what's built vs.
still planned, and the caveats worth knowing before presenting this — see
[`BLUEPRINT.md`](./BLUEPRINT.md).

---

## What the end result looks like

Once a student has answered enough questions in a topic (currently 8+),
opening their results shows something like:

- **A fault map** — a breakdown of their wrong answers by *category*
  (e.g. "62% Visualization/Spatial, 25% Procedural Error, 13% other"),
  not just a raw score.
- **A dominant weak point**, called out explicitly once there's enough
  data to be confident about it (e.g. *"Dominant weak point:
  Visualization/Spatial — 95% of your wrong answers on this topic trace
  to this category"*).
- **A remedial pathway** — a short, specific explanation of *why* that
  category of mistake happens and a 3-5 step drill sequence to fix it
  (not just "practice more").
- **A queue of targeted next questions** — pulled specifically because
  their wrong options are heaviest in the student's weak category, so the
  next few attempts either confirm the diagnosis or start closing the gap.

Below that confidence threshold, it's honest about it instead of guessing
— it'll say there isn't enough data yet, or that the pattern looks like
isolated slips rather than something systematic.

The primary way to see this is the Flask API + Next.js frontend (Phase
6, see below) — a custom-built quiz and results UI, calling the API live
as questions are answered. A Streamlit app that does the same thing in
one process, and the original terminal + static-HTML flow, both still
work and are kept around as simpler legacy alternatives (see "Legacy /
scripted alternative" below).

---

## Project layout

```
topic_taxonomy.json      the 9 error categories + what they look like per subject
schema.sql                the SQLite table definitions
seed_questions_physics_*.json   the question bank, by topic
load_questions.py         merges the seed files and loads them into acae.db
cognitive_profiler.py      turns a student's attempt log into a weak-point profile
weak_point_selector.py     picks the next questions to target that weak point
remedial_engine.py         category -> explanation + drill sequence
seed_and_simulate.py       demo/sample data: seeds a tiny DB + a synthetic biased student

api.py                     Flask REST API (primary backend, Phase 6) — thin JSON
                            wrapper around the modules above
frontend/                  Next.js app (primary frontend, Phase 6) — quiz-taking
                            and results screens, calling api.py via fetch()

app.py                     legacy: Streamlit app — quiz + results in one process
run_quiz.py                 legacy: terminal quiz — answer questions, log attempts
export_dashboard_data.py    legacy: snapshots a student's results to dashboard_data.json
dashboard.html               legacy: the results view (opens dashboard_data.json)
```

## Requirements

- Python 3.9+
- `flask` and `flask-cors`, for the primary Flask API (`pip install flask
  flask-cors`) — not needed if you're only using the legacy scripted flow
  below, since everything there is standard library
- Node.js 18.18+, for the primary Next.js frontend — not needed for any
  of the legacy alternatives
- `streamlit`, only if you're using the legacy Streamlit app
  (`pip install streamlit`)

## How to run it

All commands below assume you're in this project folder in a terminal.

### 1. Build the question database

```
python load_questions.py
```

This merges the three topic JSON files into `seed_questions_physics.json`
and loads everything into `acae.db` (created automatically). Safe to
re-run any time — it upserts rather than duplicating.

### 2. Run the Flask API

In its own terminal, from the project root:

```
pip install flask flask-cors
python api.py
```

This starts the API at `http://127.0.0.1:5000`. It's a thin JSON wrapper
around the same `cognitive_profiler.py` / `weak_point_selector.py` /
`export_dashboard_data.py` / `seed_and_simulate.py` modules the legacy
scripts below call directly — no diagnostic logic lives in `api.py`
itself. Leave this terminal running.

### 3. Run the Next.js frontend

In a **second** terminal, from the project root:

```
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. This is the primary way to use ACAE — a
custom quiz-taking screen and a results screen, both talking to the
Flask API from step 2 via `fetch()`:

- **Quiz** (`/`) — pick a student ID and topic and answer questions one
  at a time, same mechanics as `run_quiz.py` below but in the browser,
  with immediate correct/incorrect feedback per question.
- **Results** (`/results`) — the fault map (wrong answers broken down by
  category), the dominant weak point call-out once there's enough data
  to be confident about it, the remedial pathway, and the next-up
  question queue described above.

Either screen offers a **"See a sample result"** button — it calls
`POST /api/sample/generate` to seed a synthetic biased student into its
own `acae_demo.db` (never touching your real `acae.db`), then loads that
student's results from `GET /api/results/sample`. Sample results are
clearly labeled on screen, with a one-click way back to your real data.

`frontend/.env.local` points the frontend at the API
(`NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:5000` by default) — change it
if you're running the API somewhere else, then restart `npm run dev`
(Next.js only reads `.env.local` at startup).

### Legacy / scripted alternative

Two older ways to run ACAE still work and are kept around — neither is
the primary way to use it anymore, but both are handy for headless
testing, scripting against the DB directly, or if you'd rather run one
process instead of two.

**Streamlit app** — quiz and results together in one browser tab, no
separate API/frontend processes:

```
pip install streamlit
streamlit run app.py
```

It has two tabs, mirroring the Flask + Next.js flow above:

- **🧠 Quiz** — pick (or accept a default) student ID and topic in the
  sidebar and answer questions one at a time.
- **📊 My Results** — the same fault map, dominant weak point, remedial
  pathway, and next-up question queue, rebuilt live from the database on
  every answer.

It has its own **"See a sample result"** button on the Results tab, using
the same `acae_demo.db` mechanism described above.

**Terminal + static-dashboard flow** — no browser needed until the very
last step, or script against the DB directly:

**Take a quiz:**

```
python run_quiz.py
```

You'll be shown each question's stem and four options and asked to type
A/B/C/D. `student_id` and `topic_id` are both **optional** — if you don't
pass them, it defaults to a `guest_student` on whichever topic currently
has the most questions, and tells you which defaults it picked:

```
python run_quiz.py                          # uses defaults for everything
python run_quiz.py alex                       # your own student_id, default topic
python run_quiz.py alex phys_kinematics_2d    # both specified
```

Type `Q` at any point to quit early — whatever you've already answered is
saved.

**See the results:**

```
python export_dashboard_data.py
```

Same deal — `student_id` and `topic_id` are optional and default to
whichever student/topic actually has attempts logged. This writes
`dashboard_data.json`. Then open `dashboard.html` in a browser (just
double-click it, or `start dashboard.html` on Windows / `open
dashboard.html` on Mac). It reads `dashboard_data.json` and renders the
fault map, dominant weak point, remedial note, and next-up question queue
described above.

Re-run `export_dashboard_data.py` and refresh the browser tab any time you
want to see updated results after more attempts.

**Want to just look at a working example without answering 20-30 questions?**

Run the standalone demo instead — it seeds a small database and simulates
a student with a deliberately biased weak point, so the profiler has
something real to find immediately:

```
python seed_and_simulate.py
```

This writes its own `acae_demo.db` (separate from your real `acae.db`, so
it won't touch any real attempts). Point the profiler/selector/export
scripts at it with `--db acae_demo.db` to see the full diagnosis pipeline
run instantly, e.g.:

```
python cognitive_profiler.py demo_student_01 --db acae_demo.db
python export_dashboard_data.py demo_student_01 phys_kinematics_2d --db acae_demo.db
```

This is also the recommended way to demo or test the dashboard while the
real question bank is still small — swap in real attempt data once you
have it, rather than re-answering the full quiz on every test run.

## Peeking inside the database (optional)

```
sqlite3 acae.db
.tables
SELECT COUNT(*) FROM questions;
.quit
```

Requires the standalone `sqlite3` command-line tool — not required for
anything above, Python's built-in `sqlite3` module (already included with
Python) is what the scripts actually use.

## Troubleshooting

| What you see | What it means | What to do |
|---|---|---|
| `ModuleNotFoundError: No module named 'X'` | A required package isn't installed | `pip install X` |
| `FileNotFoundError` | Wrong folder, or a file hasn't been created yet | Confirm you're in the project folder; run `python load_questions.py` first if `acae.db` doesn't exist yet |
| `sqlite3.OperationalError: database is locked` | Two scripts tried to use `acae.db` at the same time | Close any other window/script touching `acae.db`, then retry |
| Dashboard shows "No attempts logged for this topic yet" | You haven't run `run_quiz.py` for that student/topic (or haven't hit the confidence threshold) | Answer more questions, or use `seed_and_simulate.py` for an instant example |
| Frontend shows "Couldn't reach the API at http://127.0.0.1:5000" | `python api.py` isn't running, or it's running on a different port than `frontend/.env.local` expects | Start `python api.py` in its own terminal first; confirm the two match |
| CORS error in the browser console | Rare — `flask-cors` didn't load | Confirm `pip install flask-cors` succeeded; `api.py` already calls `CORS(app)` |
| `npm run dev` fails immediately | Dependencies not installed, or Node too old | Run `npm install` inside `frontend/`; confirm Node 18.18+ with `node --version` |

## Caveats worth knowing before presenting this

See `BLUEPRINT.md` §8 for the full list — the short version:

- Distractor-mapping quality is everything; the seed questions were
  human-reviewed, not taken raw from an LLM.
- 8+ attempts per topic are needed before the system will commit to a
  diagnosis rather than guess — early sessions on a fresh database will
  look thin, which is expected, not broken.
- Two of the nine error categories (time-pressure collapse, calculation
  speed deficit) are detected from timing data, not from which wrong
  option a student picks.
- The Flask + Next.js split is new surface area, not new intelligence —
  none of the diagnostic logic in `cognitive_profiler.py` /
  `weak_point_selector.py` / `remedial_engine.py` changed to build it.
  The added risk is plumbing: two dev servers to keep running instead of
  one, and the API/frontend JSON contract drifting out of sync.