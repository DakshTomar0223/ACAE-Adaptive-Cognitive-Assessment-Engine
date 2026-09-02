// lib/api.ts
//
// Thin typed wrapper around the ACAE Flask API (Phase 6A). Every request
// goes through apiFetch() so error handling and the base URL are defined
// once. No data-fetching library — plain fetch(), matching the rest of
// this scaffold.

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export type Topic = {
  topic_id: string;
  name: string;
  n_questions: number;
};

export type QuizOption = {
  option_id: string;
  option_text: string;
};

export type QuizQuestion = {
  question_id: string;
  stem: string;
  difficulty: number;
  options: QuizOption[];
};

export type QuizNextResponse = {
  question: QuizQuestion | null;
  remaining: number;
  message?: string;
};

export type AnswerPayload = {
  student_id: string;
  topic_id: string;
  question_id: string;
  option_id: string;
  time_taken_sec: number;
};

export type AnswerResponse = {
  is_correct: boolean;
  correct_option_id: string;
};

// --- results / dashboard payload (Phase 6C) --------------------------------
//
// Mirrors the shape export_dashboard_data.py produces (same payload
// dashboard.html consumed in Phase 5) and that GET /api/results and
// GET /api/results/sample both return.

export type ChartDatum = {
  label: string;
  value: number;
  color?: string;
  category?: string;
};

export type SelectedQuestion = {
  question_id?: string;
  stem: string;
};

// The four states the confidence gate / weak-point selector can report.
// Kept as a literal union (not collapsed into a single "status" string
// shown verbatim) so the UI can give each one honest, distinct copy:
//   no_signal        — effectively no attempts/errors to work from yet
//   provisional       — a leading category exists but the confidence
//                        gate (attempt threshold) hasn't been met
//   no_clear_pattern — gate met, but errors are too spread out to name
//                        one dominant category
//   confident         — gate met and one category clearly dominates
export type WeakPointStatus =
  | "no_signal"
  | "provisional"
  | "no_clear_pattern"
  | "confident";

export type WeakPointInfo = {
  status: WeakPointStatus;
  dominant_category: string | null;
  share_of_errors: number | null;
  message?: string | null;
  remedial_note?: string | null;
  selected_questions?: SelectedQuestion[];
};

export type DashboardPayload = {
  total_attempts: number;
  accuracy_pct: number;
  chart_data: ChartDatum[];
  weak_point_info: WeakPointInfo;
};

export type SampleGenerateResponse = {
  status: string;
  message: string;
  db_path: string;
  student_id: string;
  topic_id: string;
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  if (!BASE_URL) {
    throw new ApiError(
      0,
      "NEXT_PUBLIC_API_BASE_URL is not set — add it to .env.local and restart the dev server."
    );
  }

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(
      0,
      `Couldn't reach the API at ${BASE_URL}. Is the Flask server running?`
    );
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.error ?? detail;
    } catch {
      // response wasn't JSON — fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }

  return (await res.json()) as T;
}

export function fetchTopics(): Promise<Topic[]> {
  return apiFetch<Topic[]>("/api/topics");
}

export function fetchNextQuestion(
  studentId: string,
  topicId: string
): Promise<QuizNextResponse> {
  const params = new URLSearchParams({
    student_id: studentId,
    topic_id: topicId,
  });
  return apiFetch<QuizNextResponse>(`/api/quiz/next?${params.toString()}`);
}

export function submitAnswer(payload: AnswerPayload): Promise<AnswerResponse> {
  return apiFetch<AnswerResponse>("/api/quiz/answer", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** GET /api/results?student_id=&topic_id= */
export function fetchResults(
  studentId: string,
  topicId: string
): Promise<DashboardPayload> {
  const params = new URLSearchParams({
    student_id: studentId,
    topic_id: topicId,
  });
  return apiFetch<DashboardPayload>(`/api/results?${params.toString()}`);
}

/** POST /api/sample/generate — (re)seeds the demo DB. */
export function generateSample(): Promise<SampleGenerateResponse> {
  return apiFetch<SampleGenerateResponse>("/api/sample/generate", {
    method: "POST",
  });
}

/** GET /api/results/sample — pinned to the demo DB/student/topic. */
export function fetchSampleResults(): Promise<DashboardPayload> {
  return apiFetch<DashboardPayload>("/api/results/sample");
}
