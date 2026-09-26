# ACAE — Adaptive Cognitive Assessment Engine
### Technical Blueprint · I2EDC Curiosity Projects 2026–27

**Team:** Areebuddin Phundreimayum, Neil Adhikari, Daksh Tomar
**Faculty Mentor:** Nalin Kumar Sharma

This is the single source of truth for what ACAE is, how it's architected,
what's actually built vs. still planned, and the hard-won rules learned
while building it. `README.md` is the short, plain-language version for
someone opening this repo for the first time — this document is the
detailed one. **Phases 0–6 are done; completed-phase sections below are
kept short on purpose — the working code and README are the source of
truth for exactly how they run.**

---

## 1. Core Thesis

Every JEE/NEET prep platform answers "did the student get it right?" ACAE
answers **"why did the student's reasoning fail, and in what recurring
shape?"**

Two students who both miss a projectile-motion question may fail for
opposite reasons — one can't hold the 2D vector picture in their head
(visualization deficit), the other holds the picture fine but drops a sign
integrating velocity (procedural/calculation deficit). Same wrong answer,
different fix. ACAE's job is to tell those two students apart and route
each to a different remedial path.

## 2. System Architecture

```
Question Bank (NCERT) ──▶ Tagging Pipeline (LLM-assisted) ──▶ Taxonomy Store (9 categories)
                                                                       │
Student Attempt ──▶ Cognitive Profiler ◀───────────────────────────────┘
                          │
                          ▼
                  Weak-Point Isolator (selects/generates "trap" questions)
                          │
                          ▼
                  Feedback / Remedial Engine (category → drill sequence)
                          │
                          ▼
                  Flask REST API (thin JSON wrapper, no diagnostic logic)
                          │
                          ▼
                  Next.js Frontend (fetch()-based quiz + results UI)
```

**Current status:** the whole pipeline above is built and wired end to
end. Phase 6 split the old single-process Streamlit app (`app.py`, kept
as a working legacy alternative) into a Flask API + Next.js frontend, so
the UI is no longer bounded by Streamlit's widget set. Phase 6.5
(visual + theming redesign) is in progress — tokens, fonts, theme toggle,
and both pages' redesigns (6E–6G) are done; **remaining work is a fix
pass (6H) for three issues found in review: typography that doesn't yet
read as modern/elegant, contrast ratios that fall short in places, and
native `<select>` dropdowns that ignore the theme system entirely** —
see §11.3.

## 3. The Cognitive Taxonomy

Nine cross-subject error categories — Conceptual Misunderstanding,
Procedural Error, Visualization/Spatial Constraint, Logical Fallacy,
Calculation Speed Deficit, Conceptual Synthesis Failure, Careless/Attention
Slip, Formula Misapplication, Time-Pressure Collapse — each with
subject-specific manifestations (e.g. Visualization/Spatial in Physics =
free-body diagram misreads; in Chemistry = 3D stereochemistry misreads).
Full definitions live in `topic_taxonomy.json`.

**Key design decision:** the taxonomy is the shared vocabulary between the
tagging pipeline (labels questions with *which* fallacy they're likely to
trigger) and the profiler (labels students with *which* fallacy they
actually exhibit). A question and a student's error meet in the same
9-category space — that's what makes "trap question targeting a specific
weak point" possible without hand-authoring traps per student.

**Only 7 of the 9 categories can be represented as an MCQ distractor.**
`time_pressure_collapse` and `calculation_speed_deficit` are timing-pattern
signals (from `time_taken_sec` in the `attempts` table, see
`cognitive_profiler.py`'s `timing_flags()`), not distractor choices. If
asked "does the taxonomy cover speed-based errors," the honest answer is
"yes, but through timing data, not distractor choice."

## 4. How "Weak-Point Isolation" Actually Works

This does **not** require solving general cognitive science. It requires:

1. **Method traces, not just right/wrong.** Every question is pre-tagged
   with which error category it's *diagnostic for* — the category a wrong
   answer most likely reveals, based on the specific distractor chosen.
2. **Distractor-mapped MCQs as the diagnostic instrument.** 4-option MCQs
   where each wrong option corresponds to one error category. Student
   picks option B → system logs "Visualization/Spatial" directly. No
   eye-tracking, no free-text NLP needed for v1.
3. **Confidence accumulates per category** (`cognitive_profiler.py`) — a
   single wrong answer is noise; a *pattern* across attempts is signal.
   `MIN_ATTEMPTS_FOR_CONFIDENCE = 8` attempts on a topic before the system
   commits to a diagnosis.
4. **`careless_attention_slip` can never be the reported dominant
   category** — the taxonomy defines it as non-recurring; if it would win
   the dominance calculation, the profiler reports "no clear systematic
   pattern" instead (`EXCLUDED_FROM_DOMINANCE`).
5. **"Trap" question selection** = once a dominant category is identified
   with enough confidence, `weak_point_selector.py` pulls next questions
   whose distractor-map is heaviest in that category, so the remedial
   engine can show the student the mechanism behind their own error. Falls
   back to repeating a question rather than crashing if the bank runs out.

This reframes "AI-generated trap questions" from an open-ended generation
problem into a **tagging + retrieval** problem.

## 5. Build Phases — status

| Phase | Scope | Status |
|---|---|---|
| **0** | Taxonomy + tagging pipeline | Done |
| **1** | Distractor-mapped question schema + SQLite store (45 hand-tagged Physics MCQs) | Done |
| **2** | Cognitive Profiler | Done |
| **3** | Weak-Point Isolator | Done |
| **4** | Remedial mapping | Done |
| **5** | Unified Streamlit UI (`app.py`) | Done |
| **6** | Flask API + Next.js frontend split | Done |
| **6.5** | Frontend visual + theming redesign — modern typography, high-contrast UI, light/dark theme toggle | 6E–6G done; **6H (fix pass: typography, contrast, dropdown theming) in progress, see §11.3** |
| **7** | Kiosk/tablet packaging | Not started — roadmap only, do this last if at all |

## 6. Tech Stack

- **Backend logic:** Python, SQLite (migrate to Postgres only if/when
  multi-device sync is needed).
- **Tagging:** Anthropic API, Haiku-class model.
- **API layer (Phase 6, done):** Flask + `flask-cors`, thin wrapper over
  `cognitive_profiler.py` / `weak_point_selector.py` / `remedial_engine.py`.
  Endpoint contract in §11.3 refs, unchanged since Phase 6.
- **Front-end (current, Phase 6, done):** Next.js, calling the Flask API
  via `fetch()` — chosen because Streamlit's widget set couldn't deliver
  custom visual design.
- **Legacy front-ends:** `app.py` (Streamlit, Phase 5) and `dashboard.html`
  (static, pre-Phase-5) — both kept working, not primary anymore.
- **Data:** NCERT-aligned question bank, hand-seeded + LLM-tagged, human
  reviewed.

## 7. What Makes This a "Curiosity Project" and Not Just Another EdTech App

The wild-idea core is the **distractor-mapped diagnostic MCQ as a cognitive
instrument** — using the *shape* of a wrong answer as structured data about
reasoning, rather than treating all wrong answers as equivalent. That's the
piece worth prototyping and defending in front of I2EDC; everything else
(kiosk packaging, UI polish) is execution.

## 8. Open Risks / Honest Caveats

State these openly in the pitch — bringing them up unprompted reads as
rigor; having the committee find them reads as a gap.

- **Distractor-mapping quality is everything.** The seed set was
  human-reviewed, not taken raw from LLM output — future batches need the
  same review pass.
- **Cold-start problem is real.** `MIN_ATTEMPTS_FOR_CONFIDENCE = 8`;
  early sessions get "provisional only" profiles. The sample/demo mode
  exists so this doesn't block demos — say this openly rather than
  overselling day-one accuracy on a fresh database.
- **"Force cognitive correction" is strong language for the committee** —
  frame it as *increasing diagnostic yield*, not guaranteed correction.
- **Two of the nine error categories aren't distractor-detectable at all**
  (see §3) — only visible as a pattern across timed attempts.
- **Splitting one process into two (Phase 6) was new surface area, not new
  intelligence** — the risk was in the plumbing (CORS, JSON contract
  drift), not in Phases 2–4's logic, which is unchanged.

## 9. Directory map (current, confirmed from repo)

```
jee-neet-practice/
├── README.md, BLUEPRINT.md, schema.sql, topic_taxonomy.json
├── seed_questions_physics.json (+ _energy/_kinematics/_mechanics variants)
│
├── backend/                          # Phase 6 — Flask API
│   ├── api.py
│   ├── cognitive_profiler.py, weak_point_selector.py, remedial_engine.py
│   ├── db_helpers.py, load_questions.py, seed_and_simulate.py
│   ├── export_dashboard_data.py, seed_questions_physics.json
│   ├── requirements.txt
│   └── acae.db, acae_demo.db          # generated — gitignored
│
├── frontend/                         # Phase 6 — Next.js app (App Router)
│   ├── app/
│   │   ├── layout.tsx, globals.css, page.tsx, page.module.css, icon.svg
│   │   ├── components/ (Header.tsx/.module.css, ThemeToggle.tsx/.module.css)
│   │   └── results/ (page.tsx, results.module.css)
│   ├── lib/api.ts                     # fetch() wrapper around the Flask API
│   ├── public/ (default Next.js assets)
│   ├── package.json, tsconfig.json, next.config.ts, eslint.config.mjs
│   ├── .env.local, AGENTS.md, CLAUDE.md, README.md
│
├── legacy/                           # Phase 5 and earlier, kept working
│   ├── app.py                         # Streamlit
│   ├── run_quiz.py, dashboard.html, dashboard_data.json, export_dashboard_data.py
│
├── start-dev.ps1                     # one-command launch: backend + frontend
└── .gitignore
```

Notable since the last pass: `backend/` carries its own copy of
`seed_questions_physics.json` and `export_dashboard_data.py` (duplicated
from repo root / `legacy/` respectively) — worth a look during Phase 6.5
or later cleanup to confirm which copy is authoritative and whether the
duplicates can be dropped. `frontend/` has no `results/` CSS module split
beyond what's listed, and already has `Header.tsx` — the shared header
component 6E's prompt asks for should extend this file, not create a new
one.

## 10. Conventions carried forward from early build sessions

- **Flags, not prose.** Judgment calls go in a `"flag"` field on the JSON
  object, not a paragraph of explanation.
- **`student_id`/`topic_id` are always optional**, falling back to a
  sensible default rather than erroring.
- **Scripts and API endpoints are safe to re-run** (upsert, not
  duplicate-on-rerun).
- **API responses reuse existing JSON shapes** (`export_dashboard_data.py`'s
  payload shape), never invent new ones.

---

## 11. Step-by-Step Instructions — Current Phase

Sections for Phases 0–6 (all done) have been condensed to short recaps —
the working code, `README.md`, and git history are the source of truth for
exactly how those were built. Full elaborate hand-off prompts for them are
no longer needed day-to-day and have been removed from this document to
keep it from growing unbounded; if you need to reconstruct one, the same
pattern used in §11.3 below (goal → files to attach → exact prompt → how
to verify) was used throughout.

### 11.0 — One-time environment setup (still applies)

```
python --version     # 3.9+, install from python.org if missing (Windows: tick "Add to PATH")
pip --version         # pip install X to fix ModuleNotFoundError
node --version         # needed from Phase 6 onward, get from nodejs.org if missing
```

### 11.1 — Recap: Phases 0–5 (all done)

| Phase | File(s) | Spot-check |
|---|---|---|
| 0 — Taxonomy | `topic_taxonomy.json` | `python -c "import json;print(len(json.load(open('topic_taxonomy.json'))['categories']))"` → `9` |
| 1 — Question bank | `schema.sql`, `load_questions.py` | `python load_questions.py` (safe to re-run) |
| 2 — Cognitive Profiler | `cognitive_profiler.py` | `python cognitive_profiler.py <student_id>` |
| 3 — Weak-Point Isolator | `weak_point_selector.py` | `python weak_point_selector.py <student_id> <topic_id>` |
| 4 — Remedial Engine | `remedial_engine.py` | `python -c "from remedial_engine import REMEDIAL_CATALOG;print(len(REMEDIAL_CATALOG))"` → `9` |
| 5 — Streamlit UI | `app.py` | `streamlit run app.py` — Quiz tab + My Results tab + "See a sample result" demo mode |

**Correctness rules these files must keep honoring** (still binding for any
future change, including Phase 6.5's frontend):
- A topic with zero wrong answers doesn't crash `dominant_category()` —
  returns `(None, 0.0)`.
- Under `MIN_ATTEMPTS_FOR_CONFIDENCE = 8`, the profile is "provisional,"
  never a false-confident diagnosis.
- `careless_attention_slip` never wins dominance (§4, rule 4).
- Question selection falls back to repeating a question, then to
  remedial-note-only, rather than crashing.

### 11.2 — Recap: Phase 6, Flask API + Next.js frontend (done)

Two processes replace the single Streamlit one:
```
python api.py                 # terminal 1 — backend, http://127.0.0.1:5000
cd frontend && npm run dev    # terminal 2 — frontend, http://localhost:3000
```
Six endpoints (`/api/topics`, `/api/quiz/next`, `/api/quiz/answer`,
`/api/results`, `/api/sample/generate`, `/api/results/sample`) are thin
JSON wrappers over the same Phase 2–4 functions the Streamlit app used —
no diagnostic logic lives in `api.py` itself. `GET /api/quiz/next`
deliberately never includes `is_correct` or `error_category` in its
response, since that JSON is what an untrusted client receives before
answering. The frontend replicates the old Streamlit quiz + results tabs
via `fetch()`, plus the same sample/demo-mode toggle. `app.py` still works
as the legacy alternative.

### 11.2a — `start-dev.ps1`: one-command dev launch

Running both processes by hand means two terminals and two `cd`s every
session. `start-dev.ps1` (project root, Windows PowerShell) automates it:
opens the backend (`python api.py`, project root) and frontend
(`npm run dev`, `frontend/`) each in their own window, so both log
streams stay visible. `./start-dev.ps1 -NoNewWindows` runs both as
background jobs in the current window instead, streaming both logs
inline — useful when running headless or over SSH. Closing a window (or
`Ctrl+C` inside it) stops that process; it doesn't touch the other one.
Purely a dev-convenience wrapper — no change to what `api.py` or
`npm run dev` themselves do.

---

### 11.3 — Phase 6.5: Frontend Theming & Visual Redesign — NOT STARTED (current target)

**Goal:** Phase 6 made the Next.js frontend functionally complete but
visually plain. Phase 6.5 makes it look intentional: **modern typography,
strong/accessible color contrast, and a proper light/dark theme system
with a user-facing toggle** — plus the branding cleanup (icon, full "ACAE"
title) already scoped here. **Visual-only — no diagnostic logic, API
contract, or state-management behavior changes anywhere in this phase.**

**Design direction to give every sub-phase below, verbatim, so the result
stays consistent across separate AI-assistant sessions:**
> Minimalist, education-focused visual design. A calm, focused
> reading/quiz-taking experience — generous white space, one clear focal
> point per screen, restrained color used only for meaning
> (correct/incorrect/category color-coding), not decoration.
> **Typography:** pick one modern, highly-legible sans (e.g. a
> humanist/grotesque sans like Inter, Manrope, or similar — self-hosted or
> via `next/font`, not a system-default stack) for UI/body text, optionally
> paired with a second display font for headings only if it stays legible
> at small sizes; let type hierarchy do most of the visual work instead of
> borders/shadows/gradients.
> **Contrast:** every text/background pairing must meet WCAG AA (4.5:1 for
> body text, 3:1 for large text/UI components) in *both* themes — treat
> this as a hard constraint, not a nice-to-have, and verify it, don't just
> assert it.
> **Theming:** implement light and dark themes as two token sets sharing
> one CSS custom-property contract (e.g. `--color-bg`, `--color-text`,
> `--color-accent`, `--color-correct`, `--color-incorrect`, ...), default
> to the user's OS preference (`prefers-color-scheme`) on first load, and
> expose a persistent manual toggle (localStorage-backed) that overrides
> it — semantic colors (correct/incorrect/category coding) must stay
> legible and keep the same *meaning* in both themes, not just invert.
> Use plain CSS (CSS Modules + CSS custom properties) — no UI component
> library — so the full range of modern CSS (grid, custom properties,
> transitions, `prefers-color-scheme`, container queries where useful) is
> actually exercised rather than delegated to a framework's defaults.

**Who this section is for:** hand the remaining lettered part below to an
AI coding assistant in its own fresh conversation, attach exactly the
files listed, paste the exact prompt given.

---

#### 6E–6G — Recap: tokens/shell, quiz redesign, results redesign (done)

| Part | Built | Files |
|---|---|---|
| 6E | Light/dark CSS custom-property token sets switched via `data-theme`, a modern sans via `next/font`, `ThemeToggle` (reads `prefers-color-scheme`, persists to `localStorage`, no flash-of-wrong-theme), `app/icon.svg`, shared `Header` (icon + wordmark + toggle), tab title/meta | `globals.css`, `layout.tsx`, `components/Header.tsx(+.module.css)`, `components/ThemeToggle.tsx(+.module.css)`, `icon.svg` |
| 6F | Quiz-taking screen (student/topic picker, question card, options, correct/incorrect feedback) restyled on the 6E tokens; same `fetch()`/state logic | `app/page.tsx`, `app/page.module.css` |
| 6G | Results screen (fault-map bar chart, dominant-weak-point call-out, remedial note, next-question queue, sample-result toggle) restyled on the 6E tokens; same `/api/results` data and status handling | `app/results/page.tsx`, `app/results/results.module.css` |

**Issues found in review, not yet fixed** (scope of 6H below):
- Typography doesn't read as "modern, elegant" yet — worth a harder look
  at font pairing/weight/spacing, not just "a `next/font` sans is loaded."
- Several text/background and UI pairings fall short of WCAG AA in
  practice — 6E/6F/6G asserted contrast, it wasn't independently
  verified, and it shows.
- **Native `<select>` dropdowns (topic picker, any other `<select>`
  elements) don't pick up theme tokens at all** — they render with the
  browser's default control chrome, so in dark theme they show as a
  light-background dropdown with barely-legible text. This is the most
  concrete bug of the three.

---

#### 6H — Fix pass: typography, contrast, and dropdown theming (current target)

**What this part builds:** a targeted fix pass on top of the 6E–6G
redesign — not a new visual style, a correction of the three issues
above — plus the same responsive/motion/accessibility sweep originally
scoped for this step, since it's the natural point to do both together.

**Files to attach:** the full `frontend/app/` directory as it stands
after 6G (tokens, header, theme toggle, quiz page, results page).

**Exact prompt to paste:**
> This is Phase 6.5 (part 6H, fix pass) of ACAE. [paste the design
> direction paragraph above]. The 6E–6G redesign (attached) is
> functionally done but has three known problems to fix, no new
> features: (1) **Typography** — the current font/type-scale doesn't read
> as modern/elegant; reconsider the font choice (or its weight, tracking,
> and line-height) and the heading/body type scale until it does, keeping
> it via `next/font`. (2) **Contrast** — audit every text/background and
> semantic-color pairing in *both* themes against WCAG AA (4.5:1 body,
> 3:1 large text/UI) using an actual contrast-checking tool, not
> eyeballing, and fix every pairing that fails — list which token pairs
> you changed and their new ratios. (3) **Dropdowns** — every `<select>`
> element (the topic/student picker, and any other native select) must
> visually follow the theme tokens in both light and dark mode: background,
> text, border, and the options-list popup itself, not just the closed
> control. If native `<select>` styling can't be made to fully respect
> `data-theme` cross-browser, replace it with a custom-styled
> listbox/combobox built from the same tokens instead of leaving it
> unthemed — same options, same `onChange` behavior, no data logic change.
> Also do the standard polish pass: responsive layout down to ~375px width
> (option buttons and category bars are the things most likely to break),
> consistent restrained transitions (page load, question-to-question,
> answer feedback, theme switch) on one shared easing/duration, visible
> focus ring on every interactive element in both themes, and `aria-live`
> on the answer-feedback region. Don't touch data-fetching or state logic
> anywhere.

**What you should get back:** updated `globals.css`/font setup, and
whichever of `Header`/`ThemeToggle`/`page`/`results` files changed to fix
the dropdown, contrast, and typography issues, plus the polish-pass CSS.

**After it responds:**
1. Copy in, `npm run dev`.
2. Open the topic/student picker dropdown in **dark theme specifically**
   — confirm it no longer shows as a light box with unreadable text.
3. Spot-check contrast with an actual tool (browser dev tools' contrast
   checker or an online WCAG checker) on the pairings the response says
   it fixed — confirm the ratios hold, don't just trust the claim.
4. Resize down to ~375px in both themes — confirm nothing overflows.
5. Tab through both pages keyboard-only in both themes — confirm a
   visible focus ring everywhere.
6. Toggle theme repeatedly across both pages — no flash, no element stuck
   in the wrong theme's color, dropdown included.
7. This is the last step of Phase 6.5 — update §5's status table row for
   6.5 to "Done" once all boxes below are checked.

**Definition of done for all of Phase 6.5 (6E–6H):**
- [ ] Browser tab shows the icon and full "ACAE — Adaptive Cognitive
      Assessment Engine" title
- [ ] Typography genuinely reads as modern/elegant, not just "a
      non-default font is loaded"
- [ ] Light/dark themes exist, default to OS preference, switchable via a
      persistent toggle, no flash-of-wrong-theme
- [ ] Every text/background and semantic-color pairing meets WCAG AA in
      both themes, **verified with a contrast tool, not eyeballed**
- [ ] Every `<select>`/dropdown follows the theme tokens in both modes,
      including the open options list
- [ ] Quiz and results pages share one visual language
- [ ] No diagnostic logic, API calls, or state handling changed anywhere
      in 6E–6H — visual-only
- [ ] Layout holds at desktop and ~375px mobile width
- [ ] Every interactive element has a visible keyboard focus state in
      both themes

---

### 11.4 — Phase 7: Kiosk / Offline Packaging (roadmap only — layman's plan)

**Goal:** take the Flask + Next.js pair and make it deployable, standalone,
on a low-spec tablet at a physical kiosk: large touch targets, a
dim/focus mode, minimal chrome, and no dependency on an internet
connection once installed.

**Not worth starting until Phase 6.5 is done and demoed.** Packaging
depends on hardware decisions (which tablet? which OS?) not made yet, so
it's roadmap-level, not exact copy-paste prompts — treat the sub-parts
below as the order to tackle it in once those decisions exist.

- **7A — Prove it works offline.** Confirm nothing at quiz-taking/results
  time makes a network request (the only network step in the whole
  project is the LLM tagging pipeline, used only when authoring new
  questions). Verify by turning off Wi-Fi and clicking through a full
  quiz + results flow.
- **7B — Package it for one-command install.** `requirements.txt` for
  Flask, `npm install` for Next.js, a `start.sh`/`start.bat` that launches
  both. If per-tablet hands-on setup isn't practical at scale, investigate
  bundling (`pyinstaller`, a static Next.js export) as its own session.
- **7C — Kiosk-mode the browser.** OS-level config on the actual tablet —
  full-screen, no address bar, auto-launch on boot. Steps depend entirely
  on the tablet OS chosen.
- **7D — Pilot on one real device** before duplicating to more kiosks —
  watch for touch targets too small, text too small at arm's length, and
  battery drain with two server processes running.

---

### 11.5 — Full pipeline, start to finish (quick reference)

**Day-to-day running of ACAE:** `./start-dev.ps1` from the project root
launches both the backend and frontend for you (see §11.2a). Manually,
it's still two commands, each in its own terminal:
```
# terminal 1 — backend
python api.py

# terminal 2 — frontend
cd frontend && npm run dev
```

**Legacy path** (Streamlit, still fully functional):
```
streamlit run app.py
```

**Rebuilding the database / exercising the pipeline directly** (useful for
debugging):
```
pip install --upgrade pip
python load_questions.py            # build the database
python run_quiz.py                  # take a quiz (repeat for more data)
python cognitive_profiler.py        # check the diagnosis
python weak_point_selector.py       # targeted next questions + remedial plan
python export_dashboard_data.py     # snapshot results for the legacy dashboard
```

**Quick sample data, no quiz-taking required** (useful for testing without
8+ real attempts):
```
python seed_and_simulate.py
python cognitive_profiler.py demo_student_01 --db acae_demo.db
python export_dashboard_data.py demo_student_01 phys_kinematics_2d --db acae_demo.db
```