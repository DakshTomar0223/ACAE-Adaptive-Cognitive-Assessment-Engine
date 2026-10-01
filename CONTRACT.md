# ACAE Backend ⇄ Frontend Contract (v1)

This is the standard every message between `backend/` and `frontend/` follows.
Its machine-readable twin is `contract/openapi.json`, generated from
`backend/api/schemas.py`. If this document and the generated file ever disagree,
the generated file wins and this document has a bug.

## 1. Principles

1. **One source of truth.** Shapes are defined once, in `backend/api/schemas.py`
   (Pydantic v2). The OpenAPI file, the TypeScript types and the tests are all
   derived from it. Nothing else may define a request or response shape.
2. **Contract first.** A field does not exist for the frontend until it is in
   `openapi.json`. The frontend never infers fields from sample output.
3. **Tolerant reader, strict writer.** The backend only adds optional fields
   within `v1`. The frontend ignores fields it does not know. Anything that
   removes, renames or re-types a field is `v2`.
4. **The API carries data and flags, never prose meant for the UI.** Judgment
   calls are enumerated flag codes (ACAE's existing "flags, not prose" rule).
   Display text lives in the frontend.
5. **The wire is dumb.** No diagnostic logic in `api/`; it validates, calls a
   service, serializes.

## 2. Transport

| Item | Rule |
|---|---|
| Base path | `/api/v1` |
| Format | JSON, UTF-8, `Content-Type: application/json` |
| Field naming | `snake_case` on the wire **and** in generated TypeScript types (no mapping layer to drift) |
| Timestamps | ISO-8601 UTC with `Z`, e.g. `2026-09-30T10:15:00Z` |
| Identifiers | strings. `student_id` and `topic_id` are optional on requests; the server resolves defaults and **echoes the resolved values** in the response |
| Numbers | confidences and proportions are floats in `[0, 1]`; durations are integer seconds with a `_sec` suffix |
| Enums | lowercase strings. `CategoryId` is generated from `topic_taxonomy.json`, so the taxonomy stays the only classification vocabulary |
| Base URL (frontend) | `NEXT_PUBLIC_API_BASE_URL`; CORS origin allow-list comes from backend env `ACAE_ALLOWED_ORIGINS` |

## 3. Response envelope

Every response, success or failure, has the same outer shape.

```jsonc
// success
{ "ok": true,  "data": { ... }, "meta": { "api_version": "v1", "request_id": "…", "generated_at": "…Z" } }

// failure
{ "ok": false, "error": { "code": "validation_error", "message": "…", "field": "selected_option", "details": {} },
  "meta": { "api_version": "v1", "request_id": "…", "generated_at": "…Z" } }
```

Illustrative schema skeleton (final code lives in `backend/api/schemas.py`):

```python
class Meta(BaseModel):
    api_version: Literal["v1"]
    request_id: str
    generated_at: datetime

class Envelope(BaseModel, Generic[T]):
    ok: Literal[True] = True
    data: T
    meta: Meta

class ErrorBody(BaseModel):
    code: ErrorCode            # closed enum, section 4
    message: str               # for logs and developers, never shown verbatim to students
    field: str | None = None
    details: dict[str, Any] = {}

class ErrorEnvelope(BaseModel):
    ok: Literal[False] = False
    error: ErrorBody
    meta: Meta
```

Lists that can grow (the Phase 7 review queue, attempt history) use
`Page[T] = { "items": [...], "next_cursor": str | null }`. Cursor, not offset.

## 4. Errors

The frontend branches on `error.code`, never on `message` or on status text.

| `code` | HTTP | Meaning |
|---|---|---|
| `validation_error` | 422 | request body or query failed schema validation; `field` names the culprit |
| `not_found` | 404 | unknown `question_id`, `topic_id` or `student_id` where one is required |
| `conflict` | 409 | idempotency key reused with a different payload |
| `upstream_unavailable` | 503 | database unreachable or locked |
| `internal_error` | 500 | anything else; body never leaks stack traces |

Running out of questions is not an error: it is a `200` carrying the `bank_exhausted_repeat` or
`remedial_note_only` flag (section 7), so nobody should invent a 404 for it.

The set is closed: adding a code is a contract change (section 9).

## 5. Endpoints (v1)

| Method | Path | Kind | Purpose |
|---|---|---|---|
| GET | `/health` | query | liveness plus `contract_hash` |
| GET | `/taxonomy` | query | the 9 categories, so the UI never hardcodes them |
| GET | `/topics` | query | selectable topics |
| GET | `/quiz/next` | query | next question for a student/topic |
| POST | `/quiz/answer` | **command** | record one attempt, return feedback |
| GET | `/results` | query | profile, dominant category, remedial note, next-question queue |
| POST | `/sample/generate` | command | create demo-mode data |
| GET | `/results/sample` | query | profile built from demo data |

These map one-to-one onto the six Phase 6 endpoints plus `/health` and
`/taxonomy`. Unversioned `/api/...` paths stay as aliases until the frontend
client is regenerated against `/api/v1`, then are removed.

## 6. Commands: the one write path

`POST /quiz/answer` is the only place the frontend changes backend state.

- The client generates `attempt_id` (UUIDv4) before sending.
- The server upserts on `attempt_id`: a retry with the same id and same payload
  returns the original feedback with no second row. The same id with a
  different payload returns `conflict`. This is ACAE's "safe to re-run" rule
  applied to HTTP.
- The response is the only place `is_correct`, `correct_option` and
  `error_category` appear.

## 7. Trust boundary and flags

Two distinct schemas, never one with optional secrets:

```python
class QuestionPublic(BaseModel):      # GET /quiz/next
    question_id: str; topic_id: str; stem: str
    options: list[OptionPublic]       # key + text only
    # no is_correct, no error_category, no distractor map

class AnswerFeedback(BaseModel):      # POST /quiz/answer, after submission
    attempt_id: str; is_correct: bool; correct_option: str
    error_category: CategoryId | None
```

A contract test walks the generated schema for `QuestionPublic` and fails if
any property named `is_correct`, `error_category`, `correct_option` or
`distractor_map` is reachable from it.

Enumerated flags (`flags: list[FlagCode]` on the object they qualify):

| `FlagCode` | Emitted when |
|---|---|
| `provisional_profile` | fewer than `MIN_ATTEMPTS_FOR_CONFIDENCE` (8) attempts |
| `no_systematic_pattern` | no dominant category, including when `careless_attention_slip` would have won |
| `timing_signal_only` | the dominant category comes from timing data, not distractor choice |
| `bank_exhausted_repeat` | selector repeated a question because the bank ran out |
| `remedial_note_only` | selector had nothing left to repeat and fell back to a note |

> The exact field sets of `/results`, `/topics` and `/quiz/next` come from the
> existing `export_dashboard_data.py` payload and `api.py` responses. Phase
> 6.6E derives them from those files rather than from this document, per the
> "reuse existing JSON shapes" convention.

## 8. Frontend client rules

1. `frontend/lib/api/` is the only code that calls `fetch()`. Pages and
   components import typed functions from it (`getNextQuestion()`,
   `submitAnswer()`); they never build URLs.
2. Types come from `npm run gen:types`, which reads `../contract/openapi.json`
   and writes `frontend/lib/generated/`. Generated files are not hand-edited.
3. The client unwraps the envelope in one place and throws a typed `ApiError`
   carrying `code`, `field` and `request_id`. Components render from `code`.
4. The client sends and checks `X-ACAE-Contract`: the backend stamps every
   response with the short hash of `openapi.json` it was built from; in
   development the client logs a warning when it differs from the hash baked
   into the generated types.
5. No mock data in `frontend/`. For development use the backend's sample mode
   (`/sample/generate`, `/results/sample`) or the real payloads in
   `contract/examples/`.
6. Needs something the contract lacks? Append it to
   `frontend/CONTRACT_REQUESTS.md` and stop. Do not invent an endpoint.

## 9. Changing the contract

| Change | Allowed in v1? |
|---|---|
| new endpoint, new optional response field, new optional request field | yes |
| new `ErrorCode` or `FlagCode` | yes; the frontend must treat unknown codes as generic failure / ignorable flag |
| removing or renaming a field, changing a type, making an optional field required, changing meaning | no, requires `v2` |

Procedure: edit `schemas.py` → `python scripts/export_contract.py` → commit
`contract/` → audit `--snapshot` → frontend handoff → audit `--check`.

## 10. Tests that keep this honest

All live in `backend/tests/` unless noted.

| Test | Fails when |
|---|---|
| `test_contract_roundtrip.py` | a real service result does not validate against its response schema |
| `test_contract_export.py` | `export_contract.py` output is not byte-identical on regeneration, or `contract/` is stale |
| `test_no_answer_leak.py` | any forbidden field is reachable from `QuestionPublic` |
| `test_taxonomy_sync.py` | `CategoryId` differs from the keys of `topic_taxonomy.json` |
| `test_answer_idempotency.py` | a repeated `attempt_id` creates a second row |
| `scripts/check_boundaries.py` | a layer imports something its rule forbids |
| `scripts/audit_frontend_integration.py --check` | `frontend/` calls an unknown path, embeds mock data, or anything outside `frontend/` changed |
