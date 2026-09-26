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
truth for exactly how they run. Standing rule: once a phase's definition-
of-done is fully checked, its lettered sub-phase instructions (design
direction, exact prompt, files-to-attach, after-response checks) get
collapsed out of Section 12 into a short recap row — see Section 12.1/12.2
for the pattern. This happens automatically as part of closing out the
phase, not on request.**

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
PYQ Sources (NTA archives, publisher sites, PDFs) ──▶ raw_archive/ (Phase 7, planned)
                                                              │
                                                              ▼
Question Bank (NCERT + archived PYQs) ──▶ Tagging Pipeline (LLM-assisted) ──▶ Taxonomy Store (9 categories)
                                                                                      │
Student Attempt ──▶ Cognitive Profiler ◀──────────────────────────────────────────────┘
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

**Current status:** the whole pipeline below "Question Bank" is built and
wired end to end. Phase 6 split the old single-process Streamlit app
(`app.py`, kept as a working legacy alternative) into a Flask API +
Next.js frontend, so the UI is no longer bounded by Streamlit's widget
set. Phase 6.5 (visual + theming redesign) is in progress — tokens,
fonts, theme toggle, and both pages' redesigns (6E–6G) are done;
**remaining work is a fix pass (6H) for three issues found in review:
typography that doesn't yet read as modern/elegant, contrast ratios that
fall short in places, and native `<select>` dropdowns that ignore the
theme system entirely** — see §12.3. **Growing the question bank from 45
hand-tagged Physics MCQs to thousands of real PYQs across JEE Main, JEE
Advanced and NEET (Phase 7) is the next target once 6.5 closes — see
§12.4.** `frontend/` is built and maintained by Google AI Studio;
everything else (`backend/`, `scrapers/`, `schema.sql`,
`topic_taxonomy.json`) is built and maintained by the team + Claude —
kept isolated in both directions by `scripts/audit_frontend_integration.py`
(§6, §8, §12.3).

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
weak point" possible without hand-authoring traps per student. Every
question ACAE ever ingests, however it arrives — hand-seeded (Phase 1) or
scraped from a PYQ archive (Phase 7) — must land in this same 9-category
space before it's usable; there is no second, parallel classification
system anywhere in the pipeline.

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

**Why this doesn't turn into spaghetti.** `cognitive_profiler.py`,
`weak_point_selector.py` and `remedial_engine.py` never need to know
*where* a question came from — hand-seeded, Streamlit-era, or scraped by
Phase 7's pipeline — only that it carries a valid distractor-map against
the 9-category taxonomy. Growing coverage (more exams, more subjects, more
years of PYQs) never means touching diagnostic logic; it only ever means
adding correctly-tagged rows to the same `questions` table. If a new
source's questions need something the schema doesn't capture (e.g. a
diagram-based stimulus, a numerical-answer-type question instead of MCQ),
that's a sign `schema.sql`/the taxonomy needs a new field or category,
never a sign the profiler should grow a source-specific branch.

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
| **6.5** | Frontend visual + theming redesign — modern typography, high-contrast UI, light/dark theme toggle | 6E–6G done; **6H (fix pass: typography, contrast, dropdown theming) in progress, see §12.3** |
| **7** | PYQ scraping & archive engine — thousands of real JEE Main / JEE Advanced / NEET questions, tagged and loaded into the existing schema | **Not started — next target, see §12.4** |
| **8** | Kiosk/tablet packaging | Not started — roadmap only, do this last if at all |

## 6. Tech Stack

- **Backend logic:** Python, SQLite (migrate to Postgres only if/when
  multi-device sync is needed, or if Phase 7's archive volume makes SQLite
  a real bottleneck — see §8).
- **Tagging:** Anthropic API, Haiku-class model.
- **Archival scraping (Phase 7, planned):** `requests`/`httpx` for static
  sources, a headless-browser fallback (`playwright`) only for sources that
  require it, `pdfplumber`/OCR (`pytesseract`) for PDF-sourced papers,
  content-hash based dedup across sources. Kept in its own `scrapers/`
  package so it never becomes a dependency of `backend/`'s runtime path —
  see §12.4.
- **API layer (Phase 6, done):** Flask + `flask-cors`, thin wrapper over
  `cognitive_profiler.py` / `weak_point_selector.py` / `remedial_engine.py`.
  Endpoint contract in §12.3 refs, unchanged since Phase 6.
- **Front-end (current, Phase 6, done):** Next.js, calling the Flask API
  via `fetch()` — chosen because Streamlit's widget set couldn't deliver
  custom visual design. **Built and maintained by Google AI Studio** —
  strong at UI, not trusted with backend/diagnostic logic here — as a
  standalone app in `frontend/`, calling `backend/`'s Flask API over
  HTTP. Google is given the full repo as read context so it understands
  data shapes and intent, but it must only ever *write* inside
  `frontend/`. The backend (`backend/`, `scrapers/`, `schema.sql`,
  `topic_taxonomy.json`) is built and maintained by the team + Claude,
  never by Google AI Studio.
- **Isolation audit:** `scripts/audit_frontend_integration.py` hashes
  every file outside `frontend/` before a Google AI Studio handoff and
  diffs against that snapshot after, on every regeneration — not a
  one-time check. See §12.3's isolation-audit sub-phase.
- **Legacy front-ends:** `app.py` (Streamlit, Phase 5) and `dashboard.html`
  (static, pre-Phase-5) — both kept working, not primary anymore.
- **Data:** NCERT-aligned question bank, hand-seeded + LLM-tagged, human
  reviewed; Phase 7 adds scraped-and-archived JEE/NEET PYQs through the
  same tagging + review path before they ever reach the live table.

## 7. What Makes This a "Curiosity Project" and Not Just Another EdTech App

The wild-idea core is the **distractor-mapped diagnostic MCQ as a cognitive
instrument** — using the *shape* of a wrong answer as structured data about
reasoning, rather than treating all wrong answers as equivalent. That's the
piece worth prototyping and defending in front of I2EDC; everything else
(kiosk packaging, UI polish, and even the PYQ archive's scale) is execution
in service of that core idea, not a second idea.

## 8. Open Risks / Honest Caveats

State these openly in the pitch — bringing them up unprompted reads as
rigor; having the committee find them reads as a gap.

- **Distractor-mapping quality is everything.** The seed set was
  human-reviewed, not taken raw from LLM output — future batches
  (including everything Phase 7 archives) need the same review pass
  before promotion into the live `questions` table.
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
- **Scraping legality/terms-of-service vary per source and are not
  blanket-safe just because the content is a government exam's previous
  year paper.** Each candidate source gets its own robots.txt/ToS check,
  recorded per-source, before any scraper is written against it (Phase
  7A) — never assumed clear because the *content* is public-interest.
- **A bad OCR/parse silently produces a bad distractor-map, the same
  failure mode as any unreviewed data source.** Scraped-and-parsed
  questions are never loaded straight into the live `questions` table;
  they sit in `raw_archive/` until parsed, tagged, and human-approved
  (Phase 7B/7D/7E) — the same "seed set was human-reviewed" discipline
  from Phase 1, applied at volume.
- **Going from 45 questions to "thousands" moves the actual bottleneck
  from tagging to human review.** The scraper and the LLM tagger can both
  run far faster than a human can sanity-check a distractor-map; Phase
  7E is designed to produce a review *queue*, not to force full
  auto-promotion, precisely so this doesn't quietly degrade tagging
  quality at scale.
- **The same official PYQ is often reproduced verbatim across many
  publisher sites.** Without content-hash dedup (Phase 7D) this inflates
  question counts and biases topic-frequency coverage stats without
  actually adding diagnostic coverage.
- **Handing the whole repo to an external tool (Google AI Studio) for
  frontend work is an isolation risk, not just a UI-quality one.** It
  sees everything so it understands the product, but it must only ever
  write inside `frontend/` — never `backend/`, `scrapers/`, `schema.sql`,
  `topic_taxonomy.json`, `raw_archive/`, or credentials. This isn't
  enforced by the prompt asking nicely; it's enforced by
  `scripts/audit_frontend_integration.py` diffing a pre-handoff file-hash
  snapshot against the post-handoff repo state, every single time the
  frontend is generated or regenerated — not just once, since a "quick
  follow-up tweak" prompt to Google AI Studio is exactly the moment scope
  creep back into `backend/` would happen unnoticed.

## 9. Directory Map (current, confirmed from repo)

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
├── scrapers/                         # Phase 7, planned — the "pantry":
│   │                                   #   source-agnostic archive/tag pipeline, never imported by backend/'s runtime path
│   ├── base_scraper.py                # planned — 7C, common fetch_year(exam, year) interface every source scraper implements
│   ├── sources/                      # planned — 7C, one file per source (NTA archive, publisher sites, ...)
│   ├── parsing.py                    # planned — 7D, OCR/text extraction, option/answer-key alignment, dedup
│   ├── tag_and_review.py             # planned — 7E, routes parsed questions through the Phase-0 tagging pipeline + review queue
│   └── load_archive.py               # planned — 7F, batch-loads human-approved rows into schema.sql's questions table
│
├── raw_archive/                      # Phase 7, planned — gitignored; immutable raw scraped dumps, pre-tagging, pre-review
│
├── scripts/                          # planned — backend/frontend isolation audit, see §12.3
│   └── audit_frontend_integration.py # planned — hashes everything outside frontend/, snapshot/diff around every Google AI Studio handoff
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
one. `scrapers/` and `raw_archive/` don't exist yet — they're Phase 7's
proposed layout, finalized in 7B, not a confirmed structure.

## 10. Conventions Carried Forward

- **Flags, not prose.** Judgment calls go in a `"flag"` field on the JSON
  object, not a paragraph of explanation.
- **`student_id`/`topic_id` are always optional**, falling back to a
  sensible default rather than erroring.
- **Scripts and API endpoints are safe to re-run** (upsert, not
  duplicate-on-rerun). This extends to every Phase 7 scraper and loader —
  re-running a scrape or a load must never duplicate rows, it must skip
  what's already archived/loaded.
- **API responses reuse existing JSON shapes** (`export_dashboard_data.py`'s
  payload shape), never invent new ones.
- **Raw and curated data are kept in separate stores, never one table with
  a "reviewed" flag doing double duty.** `raw_archive/` (unparsed,
  untagged, unreviewed) and `questions` (schema.sql, tagged and
  human-approved) are physically separate — this is the same discipline
  Phase 7's Open Risks bullets depend on, made structural rather than
  aspirational.
- **Google AI Studio only ever writes inside `frontend/`.** Backend
  ownership (`backend/`, `scrapers/`, `schema.sql`, `topic_taxonomy.json`,
  root config) stays with the team + Claude, enforced by
  `scripts/audit_frontend_integration.py` (§8, §12.3) — not just
  requested in the prompt.

---

## 11. Hand-off Self-Sufficiency Standard

This project is built across many separate sessions, and not necessarily
the same AI assistant each time — one lettered sub-phase might be done in
one chat, the next in a fresh session days later, possibly with a
different model entirely. None of those sessions share memory with any
other, and none of them have read this BLUEPRINT.md beyond whatever gets
attached to them. **The hand-off unit — one lettered sub-phase's write-up
in Section 12 — is the only context a fresh session will ever have.** If
that unit isn't self-sufficient, the hand-off has failed, regardless of
how correct the underlying plan is.

### 11.1 — What "self-sufficient" means, concretely

A sub-phase write-up is self-sufficient only if all of the following hold:

1. **No dangling references.** Never "the above," "as discussed," "per
   our conversation" — a fresh session has no "above," no prior
   discussion. If a decision was made in an earlier sub-phase, either
   inline the decision itself (what was decided, in one sentence) or
   attach the file that already records it.
2. **Open decisions are resolved or explicitly delegated, never just
   gestured at.** If Design direction says "settle which sources are
   in scope," the Prompt must either state the resolved answer or
   explicitly instruct the fresh session to decide AND record one.
3. **Files to attach is the complete, exact set the work needs** —
   nothing "obviously" available from a prior turn.
4. **The Prompt is model-agnostic.** It must read as a complete,
   stand-alone first message: no reliance on a specific AI's prior
   behavior or memory of earlier exchanges in this project.
5. **The After-response check is mechanically verifiable by the fresh
   session itself** — a command to run, a specific observable behavior —
   never something requiring the original author's judgment.

### 11.2 — Required format (standing template, applies to every phase)

Every lettered sub-phase, for every phase, must be written in exactly
this shape and order:

````
#### <ID> — <short title>

**Design direction:** <context, rationale, constraints, open decisions
this sub-phase must settle — tell a fresh session WHY it's doing this
and what to watch for, not just what file to touch. Any decision made
in an earlier sub-phase that this one depends on gets restated here in
one sentence, not referenced by "as decided above.">

**Files to attach:** `path/one.py`, `path/two.py`

**Prompt:**
> <a self-contained, imperative instruction a fresh chat with only the
> attached files can act on immediately — never "see above.">

**After-response check:** <one concrete, mechanically checkable thing
that proves the sub-phase actually worked>

---
````

The `**Prompt:**` block is not a copy of `**Design direction:**` — Design
direction is background for whoever is deciding what this sub-phase
should do; Prompt is the tightened, self-contained instruction for
whoever is about to actually do it.

**Sub-phase sizing rule (standing rule, applies to every phase from now
on):** each lettered sub-phase must cover exactly one file (or one
clearly-bounded addition to one file) and one concern, sized to fit
inside a single chat session's context without running out of tokens
mid-response. If a sub-phase would require holding more than one new
concept in play at once — e.g. "write the scraper AND parse the PDF AND
tag the result" — split it into further lettered sub-phases *before*
starting, not after hitting a context wall. This is why Phase 7 below
uses seven sub-phases (7A–7G): scraping, parsing, tagging and loading are
four genuinely separate concerns, each with its own failure mode (Open
Risks, §8), so each gets its own step.

---

## 12. Step-by-Step Instructions — Current Phase

Sections for Phases 0–6 (all done) have been condensed to short recaps —
the working code, `README.md`, and git history are the source of truth for
exactly how those were built.

### 12.0 — One-time environment setup (still applies)

```
python --version     # 3.9+, install from python.org if missing (Windows: tick "Add to PATH")
pip --version         # pip install X to fix ModuleNotFoundError
node --version         # needed from Phase 6 onward, get from nodejs.org if missing
```

### 12.1 — Recap: Phases 0–5 (all done)

| Phase | File(s) | Spot-check |
|---|---|---|
| 0 — Taxonomy | `topic_taxonomy.json` | `python -c "import json;print(len(json.load(open('topic_taxonomy.json'))['categories']))"` → `9` |
| 1 — Question bank | `schema.sql`, `load_questions.py` | `python load_questions.py` (safe to re-run) |
| 2 — Cognitive Profiler | `cognitive_profiler.py` | `python cognitive_profiler.py <student_id>` |
| 3 — Weak-Point Isolator | `weak_point_selector.py` | `python weak_point_selector.py <student_id> <topic_id>` |
| 4 — Remedial Engine | `remedial_engine.py` | `python -c "from remedial_engine import REMEDIAL_CATALOG;print(len(REMEDIAL_CATALOG))"` → `9` |
| 5 — Streamlit UI | `app.py` | `streamlit run app.py` — Quiz tab + My Results tab + "See a sample result" demo mode |

**Correctness rules these files must keep honoring** (still binding for
any future change, including Phase 7's archive expansion):
- A topic with zero wrong answers doesn't crash `dominant_category()` —
  returns `(None, 0.0)`.
- Under `MIN_ATTEMPTS_FOR_CONFIDENCE = 8`, the profile is "provisional,"
  never a false-confident diagnosis.
- `careless_attention_slip` never wins dominance (§4, rule 4).
- Question selection falls back to repeating a question, then to
  remedial-note-only, rather than crashing.

### 12.2 — Recap: Phase 6, Flask API + Next.js frontend (done)

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

### 12.2a — `start-dev.ps1`: one-command dev launch

Running both processes by hand means two terminals and two `cd`s every
session. `start-dev.ps1` (project root, Windows PowerShell) automates it:
opens the backend (`python api.py`, project root) and frontend
(`npm run dev`, `frontend/`) each in their own window, so both log
streams stay visible. `./start-dev.ps1 -NoNewWindows` runs both as
background jobs in the current window instead, streaming both logs
inline — useful when running headless or over SSH. Purely a
dev-convenience wrapper — no change to what `api.py` or `npm run dev`
themselves do.

---

### 12.3 — Phase 6.5: Frontend Theming & Visual Redesign (in progress)

**Goal:** Phase 6 made the Next.js frontend functionally complete but
visually plain. Phase 6.5 makes it look intentional: **modern typography,
strong/accessible color contrast, and a proper light/dark theme system
with a user-facing toggle** — plus the branding cleanup (icon, full "ACAE"
title). **Visual-only — no diagnostic logic, API contract, or
state-management behavior changes anywhere in this phase.**

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

**Who this section is for:** hand each lettered part below to Google AI
Studio in its own fresh conversation, attach exactly the files listed,
paste the exact prompt given. **Google AI Studio only ever writes inside
`frontend/`** — run `scripts/audit_frontend_integration.py --snapshot`
immediately before every handoff and `--check` immediately after (§8,
Conventions §10), including for 6H below and any future regeneration.

#### 6E–6G — Recap: tokens/shell, quiz redesign, results redesign (done)

| Part | Built | Files |
|---|---|---|
| 6E | Light/dark CSS custom-property token sets switched via `data-theme`, a modern sans via `next/font`, `ThemeToggle` (reads `prefers-color-scheme`, persists to `localStorage`, no flash-of-wrong-theme), `app/icon.svg`, shared `Header` (icon + wordmark + toggle), tab title/meta | `globals.css`, `layout.tsx`, `components/Header.tsx(+.module.css)`, `components/ThemeToggle.tsx(+.module.css)`, `icon.svg` |
| 6F | Quiz-taking screen (student/topic picker, question card, options, correct/incorrect feedback) restyled on the 6E tokens; same `fetch()`/state logic | `app/page.tsx`, `app/page.module.css` |
| 6G | Results screen (fault-map bar chart, dominant-weak-point call-out, remedial note, next-question queue, sample-result toggle) restyled on the 6E tokens; same `/api/results` data and status handling | `app/results/page.tsx`, `app/results/results.module.css` |

**Issues found in review, not yet fixed** (scope of 6H below):
- Typography doesn't read as "modern, elegant" yet.
- Several text/background and UI pairings fall short of WCAG AA in
  practice — asserted in 6E/6F/6G, not independently verified.
- Native `<select>` dropdowns don't pick up theme tokens at all — in dark
  theme they show as a light-background dropdown with barely-legible text.

#### 6H0 — Isolation audit: build before handing 6H to Google AI Studio

**Design direction:** frontend work now goes entirely through Google AI
Studio while `backend/`, `scrapers/`, `schema.sql` and
`topic_taxonomy.json` stay with the team + Claude — those two halves must
never silently affect each other. Mirroring the same discipline as
above, build a small isolation-audit script *before* 6H's handoff (the
first real Google AI Studio round-trip on this project) so every future
regeneration is checked the same way, not just this one: `--snapshot`
hashes every file in the repo **except** `frontend/` and gitignored paths
(`acae.db`, `acae_demo.db`, `raw_archive/`, `node_modules`, `.next`,
`__pycache__`) and stores it in a local sidecar file; `--check` recomputes
those hashes and diffs them against the stored snapshot, printing exactly
which non-frontend file(s) changed, were added, or were removed, and
exiting non-zero if anything did.

**Files to attach:** none needed — the directory map in §9 is enough
context for what "everything outside `frontend/`" covers.

**Prompt:**
> Build `scripts/audit_frontend_integration.py` for ACAE. It must support
> two modes: `--snapshot`, which computes a SHA-256 hash of every file in
> the repo except anything under `frontend/` or these gitignored paths:
> `acae.db`, `acae_demo.db`, `raw_archive/`, `node_modules/`, `.next/`,
> `__pycache__/` — then writes the hashes to a local sidecar file (e.g.
> `.frontend_audit_snapshot.json`, itself gitignored); and `--check`,
> which recomputes those hashes and diffs them against the stored
> snapshot, printing a clear list of any changed, added, or removed
> non-frontend file, and exiting non-zero if anything changed, zero if
> not. Keep the file-walk/filter logic in one function so both modes use
> it identically.

**After-response check:** run `python scripts/audit_frontend_integration.py --snapshot`,
then edit one line in a non-frontend file (e.g. add a comment to
`cognitive_profiler.py`), then run `python
scripts/audit_frontend_integration.py --check` — it must report that
exact file as changed and exit non-zero. Revert the edit, run `--check`
again — it must report no changes and exit zero.

---

#### 6H — Fix pass: typography, contrast, and dropdown theming (current target)

**Design direction:** a targeted fix pass on top of the 6E–6G redesign —
not a new visual style, a correction of the three issues above — plus the
same responsive/motion/accessibility sweep originally scoped for this
step. The 6E–6G redesign is functionally done but has three known
problems: (1) typography doesn't read as modern/elegant; (2) several
text/background pairings fail WCAG AA; (3) native `<select>` elements
ignore the theme system entirely, showing unreadable light-on-light or
dark-on-dark chrome depending on OS/browser default. Fix all three, no new
features, no data-logic changes.

**Files to attach:** the full `frontend/app/` directory as it stands
after 6G (tokens, header, theme toggle, quiz page, results page).

**Prompt:**
> This is Phase 6.5 (part 6H, fix pass) of ACAE. [paste the design
> direction paragraph from §12.3 above]. The 6E–6G redesign (attached) is
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
> visually follow the theme tokens in both light and dark mode:
> background, text, border, and the options-list popup itself, not just
> the closed control. If native `<select>` styling can't be made to fully
> respect `data-theme` cross-browser, replace it with a custom-styled
> listbox/combobox built from the same tokens instead of leaving it
> unthemed — same options, same `onChange` behavior, no data logic
> change. Also do the standard polish pass: responsive layout down to
> ~375px width, consistent restrained transitions on one shared
> easing/duration, visible focus ring on every interactive element in
> both themes, and `aria-live` on the answer-feedback region. Don't touch
> data-fetching or state logic anywhere.

**After-response check:**
0. Before pasting the prompt to Google AI Studio, run
   `python scripts/audit_frontend_integration.py --snapshot`.
1. Copy in, `npm run dev`.
2. Open the topic/student picker dropdown in **dark theme specifically**
   — confirm it no longer shows as a light box with unreadable text.
3. Spot-check contrast with an actual tool on the pairings the response
   says it fixed — confirm the ratios hold, don't just trust the claim.
4. Resize down to ~375px in both themes — confirm nothing overflows.
5. Tab through both pages keyboard-only in both themes — confirm a
   visible focus ring everywhere.
6. Toggle theme repeatedly across both pages — no flash, no element stuck
   in the wrong theme's color, dropdown included.
7. Run `python scripts/audit_frontend_integration.py --check` — it must
   report zero non-frontend changes; if it reports any, treat that as a
   failed handoff regardless of how the UI looks, and don't merge until
   resolved.
8. This is the last step of Phase 6.5 — update §5's status table row for
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
- [ ] `scripts/audit_frontend_integration.py --check` reports zero
      non-frontend changes after the Google AI Studio handoff

---

### 12.4 — Phase 7: PYQ Scraping & Archive Engine (next target)

**Goal:** grow the question bank from 45 hand-tagged Physics MCQs to
thousands of real previous-year questions (PYQs) across JEE Main, JEE
Advanced and NEET, scraped from the internet, archived, parsed, tagged
against the existing 9-category taxonomy, human-reviewed, and loaded into
the same `questions` table the Cognitive Profiler already reads —
**without the profiler, isolator, or remedial engine ever needing to
change** (§4's spaghetti-avoidance principle applies in full here).

**Phase architecture** (the "pantry" for this phase, same role
`data_platform/` plays in a data-heavy platform — build once, reused by
every future scrape):

```
PYQ Sources (NTA archives, publisher sites, PDFs)
        │  (7C: per-source scraper, rate-limited, resumable, skip-if-cached)
        ▼
raw_archive/  — immutable raw text/images/metadata, pre-parsing, pre-tagging (7B)
        │  (7D: OCR/text extraction, option/answer-key alignment, content-hash dedup)
        ▼
Tagging Pipeline  — reuses Phase 0's Anthropic-API tagger + topic_taxonomy.json (7E)
        │  (human review queue — never auto-promoted)
        ▼
questions table (schema.sql)  — the same store cognitive_profiler.py already reads (7F)
```

Nothing downstream of the `questions` table changes. A scraped-and-tagged
NEET Biology MCQ and a hand-seeded Physics MCQ are indistinguishable to
`cognitive_profiler.py` once they're loaded — that's the whole point of
routing everything through the same taxonomy (§3).

**Sub-phase sizing rule applies** (§11.2): scraping, parsing, tagging and
loading are four separate concerns with four separate failure modes
(§8's Open Risks), so each gets its own sub-phase, never combined.

---

#### 7A — Source survey and legal/ethical scoping

**Design direction:** before writing a single scraper, identify candidate
sources for JEE Main, JEE Advanced and NEET PYQs (NTA's own official
archives, NCERT-published material, established coaching/publisher sites
that republish PYQs, previously licensed question banks) and, per
source, record: whether it's a government/official archive vs.
third-party republication, what its robots.txt and terms of service say
about automated access, and whether it requires attribution or forbids
redistribution. §8's caveat is explicit: "previous year government exam
paper" content is not automatically safe to scrape from *any* site that
republishes it — the source's own terms govern, not the content's public
nature. This sub-phase produces a written decision, not code.

**Files to attach:** none (no code exists yet) — this is a research
sub-phase; attach this section (§12.4 intro + §8's Phase 7 risk bullets)
for context.

**Prompt:**
> This is Phase 7A of ACAE, a JEE/NEET adaptive assessment engine. I need
> to grow its question bank with real previous-year questions (PYQs) from
> JEE Main, JEE Advanced and NEET, scraped from the internet. Before any
> scraper is written, produce a source survey: for each realistic source
> (NTA's official archives, NCERT material, established
> publisher/coaching sites that republish PYQs), state whether it's
> official or third-party, summarize what its robots.txt and terms of
> service say about automated access and redistribution, and give a clear
> go/no-go/needs-attribution verdict per source. Output as a markdown
> table (source, URL, official?, robots.txt verdict, ToS verdict,
> decision) plus a one-paragraph recommendation for which 2–4 sources to
> build scrapers against first, prioritizing official/permissive sources
> over ambiguous ones. Save the table and recommendation as
> `scrapers/SOURCE_SURVEY.md` (create the `scrapers/` directory if it
> doesn't exist yet).

**After-response check:** `scrapers/SOURCE_SURVEY.md` exists and contains
a markdown table with at least 4 candidate sources, each with an explicit
go/no-go/needs-attribution verdict — no source left as "TBD" or "probably
fine."

---

#### 7B — Archive schema and storage design

**Design direction:** raw scraped content must never land directly in
`schema.sql`'s `questions` table — it needs its own store,
`raw_archive/`, kept structurally separate (§10's new convention) so an
unparsed or untagged row can never accidentally reach the Cognitive
Profiler. Each raw record needs: source, exam (jee_main/jee_advanced/neet),
year, subject, a stable identifier, the raw question text/image
reference, options as scraped, the answer key if available, scrape
timestamp, and a content hash (for 7D's dedup). Settle the on-disk format
(one JSON file per question vs. one JSONL file per exam-year vs. a
separate SQLite table) and record the choice and why.

**Files to attach:** `schema.sql` (for the shape `questions` already
uses, so the raw schema stays compatible with what 7F will eventually
map into it).

**Prompt:**
> This is Phase 7B of ACAE. Attached is `schema.sql`, the existing
> question-bank schema. Design the on-disk format for `raw_archive/`,
> which holds scraped-but-not-yet-tagged PYQs before they reach the
> `questions` table. Each record needs: source, exam
> (jee_main/jee_advanced/neet), year, subject, a stable per-question id,
> raw question text (and an image path if the question is diagram-based),
> options as scraped, answer key if available, scrape timestamp, and a
> content hash for later dedup. Decide between one-JSON-file-per-question,
> one-JSONL-file-per-exam-year, or a separate SQLite table, and state why,
> considering that this needs to hold thousands of records and be easy to
> re-scan for 7D's parsing pass. Write the chosen schema/format as a
> short markdown spec saved to `scrapers/ARCHIVE_SCHEMA.md`, plus a Python
> dataclass (or equivalent) representing one raw record, saved to
> `scrapers/raw_record.py`.

**After-response check:** `scrapers/ARCHIVE_SCHEMA.md` and
`scrapers/raw_record.py` both exist; the schema doc states one clearly
chosen format (not "either would work") with a concrete field list
matching the ones above, and `raw_record.py` is a runnable
dataclass/schema definition.

---

#### 7C — Scraper framework

**Design direction:** every source-specific scraper implements the same
interface so 7E/7F never need to know which source a raw record came
from — mirrors how every ACAE question is source-agnostic to the
profiler (§4). Must be rate-limited (never hammer a source), resumable
(interrupting a scrape and re-running it should not restart from zero or
re-fetch already-archived years), and idempotent (§10's "safe to re-run"
convention) — re-running a scraper for an exam/year it already has must
skip, not duplicate. Scope this sub-phase to the base interface plus one
real scraper for whichever single source 7A ranked highest — not all
sources at once (sizing rule, §11.2).

**Files to attach:** the 7A source-survey output (verdicts table), the 7B
schema/dataclass.

**Prompt:**
> This is Phase 7C of ACAE. Attached are the Phase 7A source-survey
> verdicts and the Phase 7B raw-record schema. Build `scrapers/
> base_scraper.py` defining a common interface every source scraper
> implements — at minimum a `fetch_year(exam: str, year: int) ->
> list[RawRecord]` method using 7B's record type. Then implement exactly
> one concrete scraper, in `scrapers/sources/`, against the single
> highest-ranked source from the 7A survey. It must: rate-limit its own
> requests (a configurable delay between calls), skip any
> (source, exam, year) combination already present in `raw_archive/`
> rather than re-fetching it, and be safe to interrupt and re-run without
> duplicating or corrupting partial output. Write results to
> `raw_archive/` in the format 7B specified.

**After-response check:** running the scraper twice in a row for the same
exam/year produces the same on-disk record count both times (no
duplicates), and killing it mid-run and re-running resumes rather than
restarting from zero.

---

#### 7D — Parsing, normalization and dedup

**Design direction:** many PYQ papers are PDFs; scraped HTML pages vary
wildly in structure across sources. This sub-phase turns whatever 7C
archived into clean, uniformly-shaped text: OCR/text extraction where the
source is a PDF or image, option/answer-key alignment (matching each
option A–D to its text and identifying the correct one where an answer
key is available), and content-hash-based dedup across sources so the
same official PYQ reproduced on multiple sites doesn't get counted or
tagged twice (§8's dedup risk bullet). This is a data-quality gate, not a
tagging step — 7E only ever sees records that passed this sub-phase.

**Files to attach:** `scrapers/base_scraper.py`, one sample batch of
`raw_archive/` output from 7C (a handful of real records, not the whole
archive).

**Prompt:**
> This is Phase 7D of ACAE. Attached is the Phase 7C scraper output
> format and a sample batch of raw archived records. Build
> `scrapers/parsing.py` that: (1) for PDF- or image-sourced records,
> extracts clean question/option text via OCR (`pytesseract`) or text
> extraction (`pdfplumber`) as appropriate; (2) aligns each option A–D
> with its text and, where an answer key exists, marks the correct
> option; (3) computes a content hash per question (normalized text, not
> raw bytes, so trivial whitespace/formatting differences don't defeat
> dedup) and flags exact and near-duplicate records across sources rather
> than silently dropping or silently keeping both. Output a "parsed and
> deduped" batch in a format 7E can consume, plus a short report: how many
> records parsed cleanly, how many failed parsing (and why), how many
> duplicates were found.

**After-response check:** running the parser on a batch containing one
deliberately-duplicated record (same question copied twice) flags it as
a duplicate in the report rather than silently passing both through.

---

#### 7E — Tagging and human review queue

**Design direction:** reuses the existing Phase 0 tagging pipeline
(Anthropic API + `topic_taxonomy.json`) rather than building a second
one — the whole point of the taxonomy is that it's the *only*
classification vocabulary in the system (§3). The critical constraint
from §8's Open Risks: this must produce a **review queue**, never
auto-promote tagged questions straight into the live `questions` table.
At "thousands of questions" scale, human review — not scraping, not
tagging — is the real bottleneck, and this sub-phase's job is to make
that queue usable (batched, sorted by tagger confidence or by
exam/subject, so a reviewer can work through it efficiently), not to
eliminate the review step.

**Files to attach:** the Phase 0 tagging pipeline script, `topic_taxonomy.json`,
a sample batch of 7D's parsed-and-deduped output.

**Prompt:**
> This is Phase 7E of ACAE. Attached is the existing Phase 0 tagging
> pipeline, `topic_taxonomy.json`, and a sample batch of parsed, deduped
> records from Phase 7D. Build `scrapers/tag_and_review.py` that routes
> each parsed record through the existing tagging pipeline (do not build
> a second tagger) to produce a distractor-map against the 9-category
> taxonomy, then writes the result to a review queue — a table or file a
> human reviewer can page through, showing the question, its proposed
> distractor-map, and the tagger's stated confidence, with an
> approve/reject/edit action per record. Nothing in this queue is
> auto-promoted; approval is a separate, explicit human action. Sort the
> queue so low-confidence and high-volume subjects surface first, so a
> reviewer's time goes where it matters most.

**After-response check:** a record with no reviewer action taken does not
appear anywhere in 7F's input — only explicitly-approved records do.

---

#### 7F — Bulk validation and load into `questions`

**Design direction:** extends `load_questions.py`'s existing safe-to-rerun
upsert behavior (§10) rather than writing a second loader — a
human-approved batch from 7E's queue gets inserted into `schema.sql`'s
`questions` table using the same shape `cognitive_profiler.py` already
reads, so nothing downstream changes. Must report counts per
exam/subject/year so coverage gaps are visible, and must be safe to
re-run without re-inserting already-loaded questions.

**Files to attach:** `load_questions.py`, `schema.sql`, a sample of
7E's approved-queue output.

**Prompt:**
> This is Phase 7F of ACAE. Attached is the existing `load_questions.py`,
> `schema.sql`, and a sample of human-approved records from the Phase 7E
> review queue. Build `scrapers/load_archive.py`, following
> `load_questions.py`'s existing upsert pattern (safe to re-run, no
> duplicate rows on re-run), that batch-loads only approved records into
> the `questions` table in the exact shape `cognitive_profiler.py`
> already expects. After loading, print a report: total questions loaded
> this run, and a breakdown by exam × subject × year, so gaps in coverage
> are visible at a glance.

**After-response check:** `python cognitive_profiler.py <student_id>`
still runs unmodified against a database that now also contains
Phase-7-loaded questions, with no code change to `cognitive_profiler.py`
itself.

---

#### 7G — Coverage validation

**Design direction:** once loading works, the open question is *how
much* of the intended scope (JEE Main / JEE Advanced / NEET, all major
subjects, several years) is actually covered, and where the gaps are —
this closes the loop back to §8's caveats rather than declaring victory
once the pipeline merely runs.

**Files to attach:** the Phase 7F load report format, `schema.sql`.

**Prompt:**
> This is Phase 7G of ACAE. Attached is the Phase 7F load report format
> and `schema.sql`. Build a small coverage-check script that queries the
> `questions` table and reports, as a matrix, exam × subject × year
> counts against a target coverage list (state the target list as a
> config at the top of the script, editable later). Highlight cells that
> are zero or far below the target so the team knows exactly which
> exam/subject/year combinations still need more scraping before the
> bank is considered broad enough for a real pilot.

**After-response check:** the script runs against the current database
and prints a matrix with at least one flagged gap (assuming the archive
isn't yet fully populated) — proving it actually detects under-coverage
rather than always reporting success.

---

### 12.5 — Phase 8: Kiosk / Offline Packaging (roadmap only — layman's plan)

**Goal:** take the Flask + Next.js pair and make it deployable, standalone,
on a low-spec tablet at a physical kiosk: large touch targets, a
dim/focus mode, minimal chrome, and no dependency on an internet
connection once installed.

**Not worth starting until Phase 6.5 is done and demoed, and ideally not
before Phase 7 has broadened the question bank** — a kiosk with 45
questions demos poorly regardless of how polished the UI is. Packaging
also depends on hardware decisions (which tablet? which OS?) not made
yet, so it's roadmap-level, not exact copy-paste prompts.

- **8A — Prove it works offline.** Confirm nothing at quiz-taking/results
  time makes a network request (the only network step in the whole
  project is the LLM tagging pipeline, used only when authoring new
  questions — including Phase 7's archive pipeline). Verify by turning
  off Wi-Fi and clicking through a full quiz + results flow.
- **8B — Package it for one-command install.** `requirements.txt` for
  Flask, `npm install` for Next.js, a `start.sh`/`start.bat` that launches
  both. If per-tablet hands-on setup isn't practical at scale, investigate
  bundling (`pyinstaller`, a static Next.js export) as its own session.
- **8C — Kiosk-mode the browser.** OS-level config on the actual tablet —
  full-screen, no address bar, auto-launch on boot. Steps depend entirely
  on the tablet OS chosen.
- **8D — Pilot on one real device** before duplicating to more kiosks —
  watch for touch targets too small, text too small at arm's length, and
  battery drain with two server processes running.

---

### 12.6 — Full pipeline, start to finish (quick reference)

**Day-to-day running of ACAE:** `./start-dev.ps1` from the project root
launches both the backend and frontend for you (see §12.2a). Manually,
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

**Phase 7, once built** (§12.4):
```
python -m scrapers.sources.<source_name> --exam jee_main --year 2024   # 7C: scrape one exam-year
python -m scrapers.parsing --exam jee_main --year 2024                 # 7D: parse + dedup
python -m scrapers.tag_and_review --exam jee_main --year 2024          # 7E: tag, queue for review
python -m scrapers.load_archive                                       # 7F: load approved records
python -m scrapers.check_coverage                                     # 7G: coverage matrix
```

---

## 13. Working Inside Claude Projects (and any other AI-assistant workflow)

Two small scripts automate the mechanical half of the "figure out what's
next, copy the right prompt + files into a fresh session" loop — the same
role `check_blueprint.py`/`assemble_handoff.py` play in the Nifty
project, ported to ACAE's phases and directory layout.

**`check_blueprint.py`** — checks the repo against this BLUEPRINT.md's
Phase 6.5/7 sub-phases, prints a status table, and tells you which
lettered sub-phase to work on next:
```
python check_blueprint.py              # report only, no file changes
python check_blueprint.py --apply      # also sync §5's status-table rows to match reality
python check_blueprint.py --signoff 6H # record a manually-verified sub-phase (see below)
```
Most sub-phases (7A–7G, 6H0) are checked by file existence — did the
expected output file (`scrapers/SOURCE_SURVEY.md`, `scrapers/base_scraper.py`,
etc.) actually get created. **6H is different on purpose:** typography
quality, WCAG contrast ratios, and dropdown theming are not things a
script can verify by reading file contents — 6H's definition of done
(§12.3) requires an actual contrast tool and a human looking at both
themes. `check_blueprint.py` records 6H as done only after you run
`--signoff 6H`, which you do yourself once you've actually worked through
6H's after-response checklist — the script never marks a
human-judgment sub-phase done on its own say-so.

**`assemble_handoff.py`** — pulls one lettered sub-phase's Design
direction/Prompt/Files-to-attach straight out of this document and writes
a ready-to-paste `.txt` blob:
```
python assemble_handoff.py 7C                 # normal — auto-detects the id if omitted
python assemble_handoff.py 7C --full          # ignore the stable tier, embed everything
python assemble_handoff.py 7C --lite          # strip docstrings from embedded reference-only files
python assemble_handoff.py --mark-stable path/to/file.py   # add to the stable tier once a phase closes
python assemble_handoff.py --unmark-stable path/to/file.py
python assemble_handoff.py --list-stable
```
**Rule going forward (same as Nifty's):** the moment a sub-phase's status
flips to done, mark its file(s) stable in the same breath you'd otherwise
upload them to Claude Project knowledge, so the next sub-phase that only
*references* them doesn't re-embed their full text.

Both scripts assume they live at the project root (`jee-neet-practice/`),
next to `BLUEPRINT.md`, `schema.sql`, `backend/`, and (once Phase 7
starts) `scrapers/`.