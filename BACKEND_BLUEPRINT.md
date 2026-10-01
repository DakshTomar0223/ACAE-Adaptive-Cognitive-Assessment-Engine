# ACAE — Backend Blueprint
### Technical Blueprint · I2EDC Curiosity Projects 2026–27

**Team:** Areebuddin Phundreimayum, Neil Adhikari, Daksh Tomar
**Faculty Mentor:** Nalin Kumar Sharma

This is the single source of truth for the ACAE **backend**: what it is, how
it is layered, what is built vs. still planned, and the hard-won rules learned
while building it. It covers `backend/`, `scrapers/`, `schema.sql`,
`topic_taxonomy.json`, `scripts/` and the generated `contract/`. It does **not**
describe any client. `README.md` is the short, plain-language version for
someone opening the repo for the first time; this document is the detailed one.

**Scope rule.** The backend and every client are separate projects with
separate blueprints. **The only thing that binds them is `contract/`**
(`CONTRACT.md`, generated `openapi.json`, generated `examples/`). This
document never describes what a client does with the contract, and a client's
blueprint never describes what sits behind it. If something here seems to need
a client detail to make sense, that is a gap in the contract: fix the
contract, not the boundary.

**Phases 0–6 (backend half) are done; completed-phase sections below are kept
short on purpose — the working code and README are the source of truth for
exactly how they run. Standing rule: once a phase's definition-of-done is
fully checked, its lettered sub-phase instructions (design direction, exact
prompt, files-to-attach, after-response checks) get collapsed out of Section
12 into a short recap row — see Section 12.1/12.2 for the pattern. This
happens automatically as part of closing out the phase, not on request.**

**Architecture and wire format:** §4a is the architecture standard (layers,
import rules, ownership, the seam); `contract/CONTRACT.md` is the wire
standard; §12.3b (Phase 6.6) is the build order.

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
                  Weak-Point Isolator (selects "trap" questions)
                          │
                          ▼
                  Feedback / Remedial Engine (category → drill sequence)
                          │
                          ▼
                  HTTP API (thin JSON wrapper, no diagnostic logic)
                          │
                          ▼
                  contract/  ← the only surface anything else ever sees
```

**Current status:** the whole pipeline below "Question Bank" is built and
wired end to end. Phase 6 exposed it over a Flask REST API (`api.py`); the
legacy single-process Streamlit app (`app.py`) is kept as a working
alternative that imports the modules directly. **Phase 6.6 (architecture
alignment) is planned next: it applies the Nifty platform's layering to the
backend (domain → data_platform → engine → services → api), replaces Flask with
a FastAPI app whose Pydantic schemas generate the contract, and adds
mechanical boundary and contract checks — see §12.3b.** Growing the question
bank from 45 hand-tagged Physics MCQs to thousands of real PYQs across JEE
Main, JEE Advanced and NEET (Phase 7) follows once 6.6 closes — see §12.4.

The backend does not know what consumes the contract. Whatever does is built,
owned and documented separately; the backend's obligations to it are exactly
what `contract/CONTRACT.md` says and nothing more.

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

## 4a. Architecture Standard

This section ports the structure that worked in the Nifty platform (pantry →
engine → plug-ins → API) onto ACAE's backend. The repository layout is in §9,
the wire format is `contract/CONTRACT.md`, and the build order is Phase 6.6
(§12.3b).

| Nifty | Role | ACAE equivalent |
|---|---|---|
| `data_platform/` (pantry) | the only code that knows on-disk layouts | `backend/data_platform/` — SQLite repositories, `schema.sql`, migrations, `raw_archive/` I/O |
| `engine/strategy_base.py` (3-question contract) | one interface every plug-in answers; engine never branches per strategy | `backend/engine/contracts.py` — the `Detector` interface (§4a.2) |
| `engine/simulator.py`, `stats.py` | one loop, one result schema | `engine/profiler.py`, `selector.py`, `remedial.py` — one profile schema out, whichever detectors fed it |
| `strategies/*` | plug-ins that never import each other | `engine/detectors/*` — `distractor.py`, `timing.py`, future ones (hint usage, revisit patterns) |
| `reporting/` + `api/` (read-only) | serve computed output, never recompute | `backend/services/` (use-cases) + `backend/api/` (thin HTTP) |
| `api/schemas.py` + `openapi_contract.json` | the frontend contract | `backend/api/schemas.py` → `contract/openapi.json` (generated) |

One deliberate difference: Nifty's API is read-only. ACAE has exactly one write
path (recording an answer). The contract marks it as a command and makes it
idempotent (`contract/CONTRACT.md` §6); everything else stays a query.

### 4a.2 The engine contract (Nifty's "three questions", applied)

Nifty's strategies answer three questions and nothing else. ACAE's profiler
does the same with evidence sources. A `Detector` answers:

1. **What evidence do I need?** `required_evidence()` — e.g. attempts with a
   chosen option, or attempts with `time_taken_sec`.
2. **What does that evidence imply?** `observe(attempts, taxonomy)` —
   per-category weights, each tagged with the detector's name.
3. **How sure am I?** `confidence(observation)` — so "provisional" profiles
   (`MIN_ATTEMPTS_FOR_CONFIDENCE = 8`) stay an engine rule, not a detector quirk.

The taxonomy already points at this split: seven categories are visible through
distractor choice, and `time_pressure_collapse` / `calculation_speed_deficit`
only through timing (§3). Today that split lives inside `cognitive_profiler.py`;
under this contract `distractor.py` and `timing.py` are two detectors and the
profiler merges whatever they report.

The engine never touches sqlite. It depends on small `Protocol` ports in
`engine/ports.py` (`QuestionRepository`, `AttemptRepository`); `data_platform`
satisfies them structurally without importing `engine`. Nifty did the same with
`MarketData`: the engine only asks the data layer a fixed set of questions.

**Rule carried over unchanged from Nifty:** if a new evidence source needs
something the contract doesn't offer, extend `contracts.py` with a generic
method. Never add a source-specific branch to `profiler.py`. The four
correctness rules in §12.1 become regression tests that must pass identically
before and after the refactor.

### 4a.3 Import rules (mechanically enforced)

Layers from bottom to top, and what each may import from inside `backend/`:

| Layer | May import | Must not import |
|---|---|---|
| `domain` | nothing internal | web frameworks, sqlite3, requests, anthropic |
| `data_platform` | `domain` | `engine`, `services`, `api`; web frameworks; network/LLM libraries |
| `engine` | `domain` | `data_platform`, `services`, `api`; sqlite3; web frameworks; network/LLM libraries |
| `services` | `domain`, `engine`, `data_platform` | `api`, `scrapers`, `tagging`; web frameworks; sqlite3 |
| `api` | `domain`, `services` | `engine`, `data_platform` (reach them through services); sqlite3; LLM libraries |
| `tagging` | `domain` | everything else; web frameworks |
| `scrapers` | `domain`, `data_platform`, `tagging` | `engine`, `services`, `api`; web frameworks |

Consequences: `api` cannot contain diagnostic logic because it cannot import
the engine. The runtime path (`api` → `services` → `engine`) never reaches
`scrapers` or `tagging`, which keeps the Anthropic dependency out of
quiz-taking time (and makes Phase 8's offline claim checkable).
`scripts/check_boundaries.py` enforces this with `ast` and flags any new
top-level folder under `backend/` that hasn't been classified.

### 4a.4 Ownership

| Path | Owner | Others may |
|---|---|---|
| `backend/`, `scripts/`, `schema.sql`, `topic_taxonomy.json`, root config | team + Claude | read |
| `contract/openapi.json`, `contract/examples/` | generated by `scripts/export_contract.py` | read only; never hand-edit |
| `contract/CONTRACT.md` | team + Claude | read |

`backend/` shares no code, no imports and no database access with anything
that consumes the contract. Only HTTP requests and the files in `contract/`
cross the gap.

### 4a.5 The seam

The backend's entire public surface is `contract/`. Nothing else is promised
to anyone.

1. **The backend never references a consumer.** No imports, file reads or paths
   in `backend/` point at a consumer's directory. Checked mechanically by the
   seam audit (§12.3b, 6H0 and 6.6I).
2. **A consumer never needs backend source.** It works from `contract/` alone;
   a session building a consumer is handed `contract/` and nothing from
   `backend/`.
3. **Contract freshness.** `contract/openapi.json` is generated from
   `backend/api/schemas.py`; `scripts/export_contract.py --check` fails on any
   drift.
4. **Changes reach consumers only through the contract's versioning rules**
   (`CONTRACT.md` §9).

The audit script that enforces 1–3 lives in `scripts/`, is owned by the
backend team, and is seam tooling: it is not part of either side's runtime.

### 4a.6 How the contract changes

Backend-first, because the contract is the source of truth:

1. A backend session edits `backend/api/schemas.py`.
2. `python scripts/export_contract.py` regenerates `contract/`.
3. `python scripts/audit_frontend_integration.py --snapshot`.
4. The consumer's session is handed `contract/openapi.json`,
   `contract/CONTRACT.md` and `contract/examples/`, plus its own files. Nothing
   from `backend/`.
5. `python scripts/audit_frontend_integration.py --check` must pass afterwards.

When a consumer needs something the contract lacks, it records the request in a
file it owns (`CONTRACT.md` §8.6) and stops. A human relays that request into a
backend session, which decides and follows steps 1–5. The backend never reads or
edits consumer source to find out what is wanted.

---

## 5. Build Phases — status

| Phase | Scope | Status |
|---|---|---|
| **0** | Taxonomy + tagging pipeline | Done |
| **1** | Distractor-mapped question schema + SQLite store (45 hand-tagged Physics MCQs) | Done |
| **2** | Cognitive Profiler | Done |
| **3** | Weak-Point Isolator | Done |
| **4** | Remedial mapping | Done |
| **5** | Unified Streamlit UI (`app.py`), now `legacy/` | Done |
| **6** | Flask API (six endpoints) over Phases 2–4 | Done |
| **6.6** | Architecture alignment — layered `backend/`, generated `contract/`, FastAPI + versioned envelope (6.6A–6.6I) | **Planned — see §12.3b** |
| **7** | PYQ scraping & archive engine — thousands of real JEE Main / JEE Advanced / NEET questions, tagged and loaded into the existing schema | **Not started — next target after 6.6, see §12.4** |
| **8** | Backend packaging for offline kiosk use | Not started — roadmap only, do this last if at all |

Work that happens on the consumer side of the contract (including 6.6J) is
tracked in that consumer's own blueprint, not here.

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
- **API layer (Phase 6, done; replaced in Phase 6.6):** Flask + `flask-cors`,
  thin wrapper over `cognitive_profiler.py` / `weak_point_selector.py` /
  `remedial_engine.py`. Phase 6.6 moves it to FastAPI + Pydantic v2 under
  `/api/v1` so `api/schemas.py` is the single source of the contract and
  `contract/openapi.json` is generated from it (`contract/CONTRACT.md`).
- **Data:** NCERT-aligned question bank, hand-seeded + LLM-tagged, human
  reviewed; Phase 7 adds scraped-and-archived JEE/NEET PYQs through the
  same tagging + review path before they ever reach the live table.
- **Seam audit:** `scripts/audit_frontend_integration.py` hashes every file
  outside the consumer's directory before a consumer hand-off and diffs after,
  on every regeneration (§12.3b, 6H0 and 6.6I).
- **Legacy:** `app.py` (Streamlit, Phase 5) and `dashboard.html` (static,
  pre-Phase-5) live in `legacy/`; both work, neither is primary.

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
- **A consumer reading backend internals defeats the contract.** If anything
  outside `backend/` is allowed to learn the backend's shapes from source
  instead of from `contract/`, the contract stops being the source of truth and
  drift becomes invisible. This is enforced mechanically, not by asking nicely:
  the seam audit diffs a pre-hand-off file-hash snapshot against the
  post-hand-off repo on every regeneration, and fails if `backend/` references a
  consumer or if `contract/openapi.json` no longer matches `api/schemas.py`.

## 9. Directory Map (target layout after Phase 6.6)

Until 6.6A runs, the repo is still the flat layout; this is the layout to build
toward. Layer and import rules: §4a. Any consumer of the contract lives in its
own directory with its own blueprint and is outside this map.

```
jee-neet-practice/
├── README.md, BACKEND_BLUEPRINT.md, .gitignore
├── contract/                         # THE SEAM — backend writes, consumers read
│   ├── CONTRACT.md                    #   wire standard (hand-written)
│   ├── openapi.json                   #   generated from backend/api/schemas.py
│   └── examples/                      #   generated real payloads
├── backend/                          # team + Claude
│   ├── domain/                        #   dataclasses, enums, taxonomy loader (imports nothing)
│   ├── data_platform/                 #   repositories.py, schema.sql, migrations — only code that knows storage
│   ├── engine/                        #   contracts.py, ports.py, profiler.py, selector.py, remedial.py, detectors/
│   ├── services/                      #   use-cases: topics, quiz, results, sample
│   ├── api/                           #   app.py, routers/, schemas.py, errors.py — thin
│   ├── tagging/                       #   Phase 0 LLM tagger (authoring-time only)
│   ├── scrapers/                      #   Phase 7 pipeline (authoring-time only; never on the runtime path)
│   ├── raw_archive/                   #   gitignored, immutable raw dumps (Phase 7)
│   ├── tests/
│   ├── topic_taxonomy.json, seed_questions_physics.json, requirements.txt
│   └── acae.db, acae_demo.db          #   generated — gitignored
├── scripts/
│   ├── check_boundaries.py            #   backend layer rules (stdlib only)
│   ├── export_contract.py             #   schemas.py -> contract/
│   └── audit_frontend_integration.py  #   seam audit: snapshot/diff, conformance, reverse isolation
└── legacy/                           # Streamlit app, old dashboard, Flask api.py once superseded
```

Current (pre-6.6) flat layout, for reference while migrating: Python modules
and `schema.sql` at repo root or in `backend/`, plus `legacy/`. `backend/`
carries duplicate copies of `seed_questions_physics.json` and
`export_dashboard_data.py`; 6.6A should decide which copy is authoritative and
drop the other.

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
- **The engine stays dumb on purpose (carried over from Nifty).** If a new
  evidence source needs something the engine doesn't offer, extend
  `engine/contracts.py` with a generic method — never add a source-specific
  branch to `profiler.py`.
- **Layer imports are enforced, not requested.** `scripts/check_boundaries.py`
  fails the build if `api` imports `engine`, `engine` imports `sqlite3` or a web
  framework, or the runtime path reaches `scrapers`/`tagging`.
- **One contract, generated.** Request/response shapes exist only in
  `backend/api/schemas.py`; `contract/openapi.json` is generated and never
  hand-edited.
- **The backend answers to the contract, not to a consumer.** Requests for
  missing endpoints or fields arrive via the consumer's request file (relayed by
  a human); backend sessions decide, edit `schemas.py` and regenerate.

---

## 11. Hand-off Self-Sufficiency Standard

This project is built across many separate sessions, and not necessarily
the same AI assistant each time — one lettered sub-phase might be done in
one chat, the next in a fresh session days later, possibly with a
different model entirely. None of those sessions share memory with any
other, and none of them have read this blueprint beyond whatever gets
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

### 12.2 — Recap: Phase 6, Flask API (done)

The pipeline is served over HTTP by `api.py`:
```
python api.py                 # backend, http://127.0.0.1:5000
```
Six endpoints (`/api/topics`, `/api/quiz/next`, `/api/quiz/answer`,
`/api/results`, `/api/sample/generate`, `/api/results/sample`) are thin JSON
wrappers over the same Phase 2–4 functions the Streamlit app used — no
diagnostic logic lives in `api.py` itself. `GET /api/quiz/next` deliberately
never includes `is_correct` or `error_category` in its response, since that
JSON is what an untrusted client receives before answering. `app.py` still
works as the legacy alternative and imports the modules directly. Phase 6.6G
replaces `api.py` with a FastAPI app under `/api/v1`.

---

### 12.3b — Phase 6.6: Architecture alignment (Nifty-style layering + generated contract)

**Goal:** apply the structure proven in the Nifty platform to ACAE: a layered
backend whose engine never touches storage or HTTP, one generated contract as
the backend's only public surface, and mechanical checks for both. **No
behavior change for students** — every correctness rule in §12.1 must hold
identically before and after. The standards are in §4a (layers, import rules,
ownership, the seam) and `contract/CONTRACT.md` (wire format); this section is
the build order.

**When:** before Phase 7 (so scrapers are built into the new layout). Do not
land the layout move (6.6A) while a consumer hand-off is in flight. Until 6.6G
reaches parity, the Flask `api.py` and `legacy/` keep working.

**Consumer side:** the consumer's adoption of the generated contract (6.6J) is
its own work, tracked in its own blueprint. The backend's only obligation is
that `contract/` is current and the seam audit passes when that work starts.

**Hand-off note:** `check_blueprint.py` and `assemble_handoff.py` match
sub-phase IDs by pattern; confirm they accept `6.6A`-style IDs (or rename the
IDs) before relying on them for this phase. Sub-phase write-ups follow §11.2.

---

#### 6H0 — Seam audit script (built; spec kept because 6.6I extends it)

**Design direction:** the consumer side of the contract is built by a
separate tool while `backend/`, `scrapers/`, `schema.sql` and
`topic_taxonomy.json` stay with the team + Claude — those two halves must
never silently affect each other. Build a small isolation-audit script *before*
the first consumer round-trip so every future regeneration is checked the same
way, not just the first: `--snapshot`
hashes every file in the repo **except** `frontend/` and gitignored paths
(`acae.db`, `acae_demo.db`, `raw_archive/`, `node_modules`, `.next`,
`__pycache__`) and stores it in a local sidecar file; `--check` recomputes
those hashes and diffs them against the stored snapshot, printing exactly
which non-frontend file(s) changed, were added, or were removed, and
exiting non-zero if anything did.

**Files to attach:** none needed — the directory map in §9 is enough
context for what "everything outside the consumer's directory" covers.

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

#### 6.6A — Repository layout move

**Design direction:** purely mechanical. Create `backend/`, `contract/`,
`scripts/` per the layout in §9 and move existing
files without editing logic: Python modules and `schema.sql`,
`topic_taxonomy.json`, `requirements.txt` into `backend/`; `app.py` and the
dashboard files stay in `legacy/`; any directory not named here is left
untouched. Fix only import
paths and file paths that the move breaks. Phase 7's `scrapers/` and
`raw_archive/` will later live under `backend/`.

**Files to attach:** the repo tree listing (output of `tree -L 3`, excluding
`node_modules`, `.next`, `.git`).

**Prompt:**
> This is Phase 6.6A of ACAE. Move the repository into this layout without
> changing any logic: `backend/` (all Python modules, `schema.sql`,
> `topic_taxonomy.json`, `requirements.txt`, tests), `contract/` (empty, with a
> `.gitkeep`), `scripts/`, `legacy/` (unchanged).
> Update only the imports and relative paths that the move breaks, and make every file path in Python anchor to `__file__`
> rather than the current directory. Do not rename functions, edit behavior,
> or touch any directory not named above. Print a list of every file you
> moved and every line you had to edit beyond the move itself.

**After-response check:** `cd backend && python -m pytest` (or the existing
spot-check commands in §12.1) passes exactly as before, the backend starts
from its new location, and the seam audit (`python
scripts/audit_frontend_integration.py --check`) reports no changes outside
`backend/`, `contract/`, `scripts/` and `legacy/`.

---

#### 6.6B — Domain types and engine contract (no behavior)

**Design direction:** this is Nifty's `strategy_base.py` moment. Create
`backend/domain/` (dataclasses `Question`, `Attempt`, `CategoryEvidence`,
`Profile`, enums, and a loader that reads `topic_taxonomy.json`; imports
nothing internal) and `backend/engine/contracts.py` + `engine/ports.py` defining
the `Detector` interface (`required_evidence()`, `observe(attempts, taxonomy)`,
`confidence(observation)`) and the `QuestionRepository` / `AttemptRepository`
`Protocol`s. Types and interfaces only; nothing is wired in yet.

**Files to attach:** `backend/schema.sql`, `backend/topic_taxonomy.json`,
`backend/cognitive_profiler.py`.

**Prompt:**
> This is Phase 6.6B of ACAE. Attached are the SQLite schema, the 9-category
> taxonomy, and the current cognitive profiler. Create `backend/domain/` with
> dataclasses mirroring the tables and the profiler's return values, plus a
> taxonomy loader; it must import nothing from the rest of the repo and no
> web, database or network library. Create `backend/engine/contracts.py`
> with a `Detector` abstract base class answering exactly three questions:
> `required_evidence()`, `observe(attempts, taxonomy)` returning per-category
> weights tagged with the detector's name, and `confidence(observation)`.
> Create `backend/engine/ports.py` with `QuestionRepository` and
> `AttemptRepository` as `typing.Protocol` classes covering exactly the
> queries the profiler, selector and remedial engine currently make. Do not
> modify `cognitive_profiler.py` or any existing file.

**After-response check:** `python -c "import domain, engine.contracts,
engine.ports"` from `backend/` succeeds, and `python
scripts/check_boundaries.py` exits 0.

---

#### 6.6C — Repositories in `data_platform/`

**Design direction:** `data_platform/` becomes the only code that knows
`schema.sql` and the SQLite file, the way Nifty's `cache.py` is the only code
that knows parquet layouts. Implement the two ports from 6.6B on top of the
existing queries in `db_helpers.py`. `data_platform` must import only `domain`
and satisfy the ports structurally. Keep `db_helpers.py` working for legacy
callers until 6.6E retires its use.

**Files to attach:** `backend/db_helpers.py`, `backend/schema.sql`,
`backend/engine/ports.py`, `backend/domain/` (all files).

**Prompt:**
> This is Phase 6.6C of ACAE. Attached are the existing SQLite helpers, the
> schema, the repository Protocols in `engine/ports.py`, and the domain
> dataclasses. Create `backend/data_platform/repositories.py` implementing both
> Protocols against SQLite, returning domain dataclasses, reusing the SQL in
> `db_helpers.py`. Writes must be upserts so re-running never duplicates rows.
> The database path must come from one config function anchored to
> `__file__`. Import only `domain` and the standard library. Do not modify
> `db_helpers.py`.

**After-response check:** a test in `backend/tests/test_repositories.py`
loads the demo database (`acae_demo.db`), reads questions and attempts through
the repositories, and writes the same attempt twice leaving exactly one row;
`python scripts/check_boundaries.py` exits 0.

---

#### 6.6D — Detectors and profiler refactor

**Design direction:** split the profiler's two evidence paths into plug-ins:
`engine/detectors/distractor.py` (the seven distractor-visible categories) and
`engine/detectors/timing.py` (`time_pressure_collapse`,
`calculation_speed_deficit`, from `time_taken_sec`). `profiler.py` merges
whatever detectors report. The profiler's rules are fixed and must stay:
zero wrong answers returns `(None, 0.0)`; under
`MIN_ATTEMPTS_FOR_CONFIDENCE = 8` the profile is provisional;
`careless_attention_slip` never wins dominance; selection falls back to a
repeated question, then a remedial note, instead of crashing. Write the
regression tests against the **old** code first, then refactor.

**Files to attach:** `backend/cognitive_profiler.py`,
`backend/weak_point_selector.py`, `backend/remedial_engine.py`,
`backend/engine/contracts.py`, `backend/engine/ports.py`.

**Prompt:**
> This is Phase 6.6D of ACAE. Step 1: write `backend/tests/test_profiler_rules.py`
> asserting the four rules above against the current, unmodified
> `cognitive_profiler.py` and `weak_point_selector.py`, plus a golden test that
> records the profile output for a fixed synthetic attempt history. Confirm
> they pass. Step 2: refactor into `backend/engine/detectors/distractor.py`,
> `backend/engine/detectors/timing.py`, and `backend/engine/profiler.py`
> (merges detector output, applies the dominance and provisional rules),
> moving `weak_point_selector.py` and `remedial_engine.py` to
> `backend/engine/selector.py` and `remedial.py`. The engine may import only
> `domain` and must read data only through the ports. Re-run the step 1 tests
> unchanged; the golden output must be identical.

**After-response check:** `python -m pytest backend/tests/test_profiler_rules.py`
passes with the golden test byte-identical to its pre-refactor recording, and
`python scripts/check_boundaries.py` exits 0.

---

#### 6.6E — Services layer

**Design direction:** one function per use-case the API needs, composing
engine plus repositories and returning domain objects (never HTTP shapes, never
raw rows): `list_topics`, `next_question`, `record_answer` (idempotent on
`attempt_id`), `build_results`, `generate_sample`, `sample_results`. Flags from
CONTRACT.md section 7 are produced here as plain enum values.

**Files to attach:** `backend/api.py` (the current Flask app),
`backend/engine/profiler.py`, `backend/engine/selector.py`,
`backend/engine/remedial.py`, `backend/data_platform/repositories.py`,
`backend/seed_and_simulate.py`.

**Prompt:**
> This is Phase 6.6E of ACAE. Attached is the current Flask `api.py`, the
> refactored engine, the repositories, and the demo-data seeder. Create
> `backend/services/` with one module per use-case (`topics`, `quiz`,
> `results`, `sample`) exposing the functions `list_topics`, `next_question`,
> `record_answer`, `build_results`, `generate_sample`, `sample_results`. Each
> composes the engine and repositories, returns domain dataclasses, and
> resolves default `student_id`/`topic_id` itself, returning the resolved
> values. `record_answer` takes a client-supplied `attempt_id` and is
> idempotent: same id plus same payload returns the original feedback; same id
> plus different payload raises a `ConflictError` defined in `services/errors.py`.
> Emit flags as an enum (`provisional_profile`, `no_systematic_pattern`,
> `timing_signal_only`, `bank_exhausted_repeat`, `remedial_note_only`). No HTTP,
> sqlite3, or framework imports.

**After-response check:** `python -m pytest backend/tests/test_services.py`
covers a repeated `attempt_id` (one row), a conflicting `attempt_id`
(`ConflictError`), and each flag; `python scripts/check_boundaries.py`
exits 0.

---

#### 6.6F — API schemas, envelope and errors

**Design direction:** this file *is* the contract. Define the envelope, error
model, `ErrorCode`, `FlagCode`, `CategoryId` (generated from
`topic_taxonomy.json`), and one request/response model per endpoint in
`contract/CONTRACT.md` section 5. Derive response field sets from what the
current Flask endpoints and `export_dashboard_data.py` actually return (reuse
existing JSON shapes). `QuestionPublic` and `AnswerFeedback` stay separate
schemas (CONTRACT.md section 7).

**Files to attach:** `contract/CONTRACT.md`, `backend/api.py`,
`backend/export_dashboard_data.py`, `backend/topic_taxonomy.json`.

**Prompt:**
> This is Phase 6.6F of ACAE. Attached are the wire-format standard, the
> current Flask API, and the dashboard payload exporter. Create
> `backend/api/schemas.py` (Pydantic v2) and `backend/api/errors.py`
> implementing CONTRACT.md: `Meta`, `Envelope[T]`, `ErrorEnvelope`,
> `ErrorCode`, `FlagCode`, `Page[T]`, `CategoryId` built from
> `topic_taxonomy.json`, and a request/response model for every endpoint in
> CONTRACT.md section 5. Base every response field set on the existing
> endpoint output, not on the examples in CONTRACT.md. Use `snake_case`
> everywhere. `QuestionPublic` must not contain `is_correct`,
> `error_category`, `correct_option` or any distractor map, directly or via a
> nested model. Import only `domain` and `services` types plus pydantic.

**After-response check:** `python -m pytest backend/tests/test_contract_roundtrip.py
backend/tests/test_no_answer_leak.py backend/tests/test_taxonomy_sync.py`
passes; the round-trip test feeds real service output from the demo database
through each response model.

---

#### 6.6G — FastAPI routers (parity with Flask)

**Design direction:** thin HTTP only: parse, call a service, wrap in the
envelope, map exceptions to `ErrorCode`s, stamp `X-ACAE-Contract` and
`request_id`. Mount under `/api/v1` and keep unversioned `/api/...` aliases
until every consumer has moved to `/api/v1`. Allowed origins come from
`ACAE_ALLOWED_ORIGINS`. Move Flask's `api.py` to `legacy/` only once parity
tests pass.

**Files to attach:** `backend/api/schemas.py`, `backend/api/errors.py`,
`backend/services/` (all files), `backend/api.py` (current Flask, for
reference), `contract/CONTRACT.md`.

**Prompt:**
> This is Phase 6.6G of ACAE. Create `backend/api/app.py` (FastAPI) and
> `backend/api/routers/` with one router per resource, implementing every
> endpoint in CONTRACT.md section 5 under `/api/v1`, plus unversioned
> `/api/...` aliases for the six original endpoints. Each handler validates
> input, calls exactly one `services` function, and returns the envelope;
> it must contain no diagnostic logic and import nothing from `engine` or
> `data_platform`. Map `ConflictError`, not-found, validation and unexpected
> exceptions to the `ErrorCode` table, never leaking stack traces. Add
> middleware that sets `X-ACAE-Contract` (short hash of
> `contract/openapi.json`) and a `request_id`, and configure CORS from
> `ACAE_ALLOWED_ORIGINS`. Add `fastapi` and `uvicorn` to
> `backend/requirements.txt`.

**After-response check:** `python -m pytest backend/tests/test_api.py` runs
each endpoint through FastAPI's test client and asserts (a) the envelope
shape, (b) `GET /api/v1/quiz/next` contains none of the forbidden fields in
its raw JSON, (c) posting the same `attempt_id` twice creates one row, and
`uvicorn api.app:app` starts from `backend/`.

---

#### 6.6H — Contract export and drift tests

**Design direction:** Nifty's 7B rule: the contract regenerates byte-identical.
`scripts/export_contract.py` writes `contract/openapi.json` (sorted keys, stable
formatting) and `contract/examples/*.json` (real payloads from the demo
database through the real services). `--check` regenerates in memory and exits
non-zero on any difference.

**Files to attach:** `backend/api/app.py`, `backend/api/schemas.py`,
`contract/CONTRACT.md`.

**Prompt:**
> This is Phase 6.6H of ACAE. Create `scripts/export_contract.py` that imports
> the FastAPI app, writes its OpenAPI document to `contract/openapi.json` with
> sorted keys and two-space indentation, and writes one example response per
> endpoint to `contract/examples/` using the demo database. Support `--check`:
> regenerate in memory, compare to the files on disk, print which differ, exit
> non-zero if any do. Anchor all paths to `__file__`. Add
> `backend/tests/test_contract_export.py` that runs the script twice and
> asserts byte-identical output.

**After-response check:** run `python scripts/export_contract.py`, then
`python scripts/export_contract.py --check` (exit 0); change one field name in
`schemas.py` and run `--check` again: it must exit non-zero and name
`contract/openapi.json`.

---

#### 6.6I — Audit script: two-way isolation and contract conformance

**Design direction:** extends the Phase 6H0 audit (snapshot/diff of everything
outside `frontend/`) with the checks in §4a.5:
conformance of `frontend/` calls against `contract/openapi.json`, no embedded
mock data, no backend reference to `frontend/`, and contract freshness via
`export_contract.py --check`. `scripts/check_boundaries.py` (already written,
stdlib only) is invoked by `--check` too.

**Files to attach:** `scripts/audit_frontend_integration.py`,
`scripts/check_boundaries.py`, `scripts/export_contract.py`,
`contract/openapi.json`.

**Prompt:**
> This is Phase 6.6I of ACAE. Extend `scripts/audit_frontend_integration.py`'s
> `--check` so that, in addition to the existing snapshot diff, it: (1) scans
> `frontend/` source for API paths and HTTP methods used and fails if any is
> absent from `contract/openapi.json`; (2) fails if `frontend/` contains
> hard-coded question or result data (objects with `stem` or `error_category`
> keys in non-generated source); (3) fails if any `.py` file under `backend/`
> references the string `frontend/` in an import or file path; (4) runs
> `scripts/export_contract.py --check` and `scripts/check_boundaries.py` and
> fails if either does. Each failure prints the file and line. Keep the
> existing `--snapshot` behavior unchanged.

**After-response check:** with a clean tree `--check` exits 0; add
`fetch("/api/v1/invented")` to a file under `frontend/lib/` and it exits
non-zero naming that line; add `import frontend` to a backend file and it
exits non-zero.

---

#### 6.6J — Consumer adoption of the generated contract (not a backend sub-phase)

Tracked in the consumer's own blueprint. Nothing here changes; the backend
only needs `contract/` to be current and `scripts/audit_frontend_integration.py
--check` to pass before and after.

---

**Definition of done for Phase 6.6:**
- [ ] Repo matches the §9 layout; `legacy/` still runs
- [ ] `scripts/check_boundaries.py` exits 0 on `backend/`
- [ ] Profiler rule tests and golden test pass unchanged before and after the refactor
- [ ] `backend/api/` contains no diagnostic logic and imports neither `engine` nor `data_platform`
- [ ] `contract/openapi.json` regenerates byte-identical; `--check` passes
- [ ] `GET /api/v1/quiz/next` never exposes `is_correct`, `error_category` or `correct_option`
- [ ] Repeating an `attempt_id` never creates a second row
- [ ] `scripts/audit_frontend_integration.py --check` passes in both directions
- [ ] §5's status row for 6.6 updated to Done, and its sub-phases collapsed into a recap row in §12.2

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

### 12.5 — Phase 8: Backend Packaging for Offline Use (roadmap only — layman's plan)

**Goal:** make the backend deployable, standalone, on low-spec kiosk hardware
with no dependency on an internet connection once installed.

**Not worth starting until Phase 6.6 is done, and ideally not before Phase 7
has broadened the question bank** — a kiosk with 45 questions demos poorly.
Packaging also depends on hardware decisions (which device? which OS?) not made
yet, so it's roadmap-level, not exact copy-paste prompts.

- **8A — Prove it works offline.** Confirm nothing on the runtime path
  (`api` → `services` → `engine` → `data_platform`) makes a network request. The
  only network steps in the whole backend are authoring-time: the LLM tagger and
  Phase 7's scrapers. `scripts/check_boundaries.py` already forbids runtime
  layers from importing `requests`, `httpx` and `anthropic`, so this is
  checkable, not just asserted. Verify by turning off Wi-Fi and exercising every
  contract endpoint (quiz, answer, results, sample).
- **8B — Package it for one-command install.** `requirements.txt`, one start
  command (`uvicorn api.app:app`), and the database file in a known location. If
  per-device setup isn't practical at scale, investigate bundling (`pyinstaller`)
  as its own session.
- **8C — Pilot on one real device** before duplicating — watch memory and
  battery drain with the server running.

---

### 12.6 — Full backend pipeline, start to finish (quick reference)

**Serving the contract:**
```
python api.py                         # until 6.6G (Flask, legacy aliases)
cd backend && uvicorn api.app:app     # from 6.6G (FastAPI, /api/v1)
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
role `check_blueprint.py`/`assemble_handoff.py` play in the Nifty project.

**`check_blueprint.py`** — checks the repo against this blueprint's
sub-phases, prints a status table, and tells you which lettered sub-phase to
work on next. Most sub-phases are checked by file existence. Sub-phases that
need human judgment are recorded done only through an explicit
`--signoff <ID>` that you run after working through that sub-phase's
after-response checklist; the script never marks a human-judgment sub-phase
done on its own say-so.

**`assemble_handoff.py`** — pulls one lettered sub-phase's Design
direction/Prompt/Files-to-attach straight out of this document and writes a
ready-to-paste `.txt` blob. Rule: the moment a sub-phase's status flips to done,
mark its file(s) stable (`--mark-stable`) so the next sub-phase that only
*references* them doesn't re-embed their full text.

**After the blueprint split:** both scripts were written against a single
`BLUEPRINT.md`. They need a way to be pointed at a specific blueprint file
(for example a `--blueprint` argument), and `scripts/check_boundaries.py`'s
docstring should cite `BACKEND_BLUEPRINT.md` §4a.3 (section numbers are
unchanged). Both scripts assume they live at the project root, next to
`BACKEND_BLUEPRINT.md`, `backend/` and `contract/`.
