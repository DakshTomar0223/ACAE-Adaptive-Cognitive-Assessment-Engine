"use client";

import { useCallback, useEffect, useState } from "react";
import styles from "./results.module.css";
import {
  ApiError,
  ChartDatum,
  DashboardPayload,
  Topic,
  WeakPointStatus,
  fetchResults,
  fetchSampleResults,
  fetchTopics,
  generateSample,
} from "@/lib/api";

type Phase = "setup" | "loading" | "loaded" | "error";

// Fallback categorical classes for chart_data entries that don't carry
// their own `color` — 9 slots to match the taxonomy's 9 error categories.
// Defined in results.module.css as theme-aware CSS custom properties
// (cat0/cat1/cat2 reuse the app's accent/correct/incorrect tokens; the
// rest have their own light/dark pair) rather than fixed hex, so the
// chart doesn't wash out or misread when the theme switches.
const PALETTE_CLASSES = [
  "cat0",
  "cat1",
  "cat2",
  "cat3",
  "cat4",
  "cat5",
  "cat6",
  "cat7",
  "cat8",
] as const;

// Copy + visual tone per confidence-gate status. Each status gets its own
// honest framing rather than being squashed into one generic message —
// "provisional" and "confident" both name a leading category, but only
// one of them is asserting it with confidence.
const STATUS_META: Record<
  WeakPointStatus,
  { badge: string; tone: keyof typeof toneClass; fallbackHeading: string }
> = {
  no_signal: {
    badge: "No signal yet",
    tone: "neutral",
    fallbackHeading: "Not enough data yet",
  },
  provisional: {
    badge: "Provisional — below confidence gate",
    tone: "amber",
    fallbackHeading: "A pattern may be emerging",
  },
  no_clear_pattern: {
    badge: "Confidence gate met",
    tone: "teal",
    fallbackHeading: "No single category dominates",
  },
  confident: {
    badge: "Confidence gate met",
    tone: "coral",
    fallbackHeading: "Dominant weak point identified",
  },
};

const toneClass = {
  neutral: "toneNeutral",
  amber: "toneAmber",
  teal: "toneTeal",
  coral: "toneCoral",
} as const;

export default function ResultsPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [topicsLoading, setTopicsLoading] = useState(true);
  const [topicsError, setTopicsError] = useState<string | null>(null);

  const [studentId, setStudentId] = useState("");
  const [topicId, setTopicId] = useState("");

  const [phase, setPhase] = useState<Phase>("setup");
  const [payload, setPayload] = useState<DashboardPayload | null>(null);
  const [isSample, setIsSample] = useState(false);
  const [viewedStudentId, setViewedStudentId] = useState("");
  const [viewedTopicId, setViewedTopicId] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setTopicsLoading(true);
    fetchTopics()
      .then((data) => {
        if (cancelled) return;
        setTopics(data);
        setTopicsError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setTopicsError(
          err instanceof ApiError ? err.message : "Couldn't load topics."
        );
      })
      .finally(() => {
        if (!cancelled) setTopicsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadLive = useCallback(async (sid: string, tid: string) => {
    setPhase("loading");
    setErrorMessage(null);
    try {
      const data = await fetchResults(sid, tid);
      setPayload(data);
      setIsSample(false);
      setViewedStudentId(sid);
      setViewedTopicId(tid);
      setPhase("loaded");
    } catch (err) {
      setErrorMessage(
        err instanceof ApiError ? err.message : "Couldn't load results."
      );
      setPhase("error");
    }
  }, []);

  const loadSample = useCallback(async () => {
    setPhase("loading");
    setErrorMessage(null);
    try {
      const generated = await generateSample();
      const data = await fetchSampleResults();
      setPayload(data);
      setIsSample(true);
      setViewedStudentId(generated.student_id);
      setViewedTopicId(generated.topic_id);
      setPhase("loaded");
    } catch (err) {
      setErrorMessage(
        err instanceof ApiError ? err.message : "Couldn't load sample results."
      );
      setPhase("error");
    }
  }, []);

  const handleViewResults = () => {
    const sid = studentId.trim();
    if (!sid || !topicId) return;
    void loadLive(sid, topicId);
  };

  const handleSwitchToLive = () => {
    setPhase("setup");
    setPayload(null);
    setIsSample(false);
    setErrorMessage(null);
  };

  const handleRetry = () => {
    if (isSample) {
      void loadSample();
    } else if (viewedStudentId && viewedTopicId) {
      void loadLive(viewedStudentId, viewedTopicId);
    } else {
      setPhase("setup");
    }
  };

  const canView = studentId.trim().length > 0 && topicId.length > 0;

  return (
    <div className={styles.page}>
      <header className={styles.intro}>
        <h1 className={styles.title}>Diagnostic results</h1>
        <p className={styles.subtitle}>
          Every wrong answer is a vote for a specific kind of mistake. Once
          enough votes are in for a topic, the dominant pattern gets named
          and a short drill queue is built around it.
        </p>
      </header>

      {phase === "loaded" && payload && isSample && (
        <div className={styles.sampleBanner}>
          <span>
            <strong>Sample data</strong> — this is a simulated student, not a
            real session.
          </span>
          <button className={styles.linkButton} onClick={handleSwitchToLive}>
            Switch to live results
          </button>
        </div>
      )}

      {phase === "loaded" && payload && !isSample && (
        <div className={styles.sessionBar}>
          <div className={styles.sessionInfo}>
            <strong>{viewedStudentId}</strong> · {viewedTopicId}
          </div>
          <button className={styles.linkButton} onClick={handleSwitchToLive}>
            View a different student or topic
          </button>
        </div>
      )}

      {phase === "setup" && (
        <SetupCard
          studentId={studentId}
          onStudentIdChange={setStudentId}
          topicId={topicId}
          onTopicIdChange={setTopicId}
          topics={topics}
          topicsLoading={topicsLoading}
          topicsError={topicsError}
          canView={canView}
          onView={handleViewResults}
          onSample={() => void loadSample()}
        />
      )}

      {phase === "loading" && (
        <p className={styles.skeleton} aria-live="polite">
          Loading results…
        </p>
      )}

      {phase === "loaded" && payload && <ResultsDashboard payload={payload} />}

      {phase === "error" && (
        <div className={`${styles.statusCard} ${styles.errorCard}`} role="alert">
          <h2 className={styles.statusHeading}>Something went wrong</h2>
          <p className={styles.statusBody}>{errorMessage}</p>
          <button className={styles.primaryButton} onClick={handleRetry}>
            Try again
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function SetupCard({
  studentId,
  onStudentIdChange,
  topicId,
  onTopicIdChange,
  topics,
  topicsLoading,
  topicsError,
  canView,
  onView,
  onSample,
}: {
  studentId: string;
  onStudentIdChange: (v: string) => void;
  topicId: string;
  onTopicIdChange: (v: string) => void;
  topics: Topic[];
  topicsLoading: boolean;
  topicsError: string | null;
  canView: boolean;
  onView: () => void;
  onSample: () => void;
}) {
  return (
    <div className={styles.setupCard}>
      <div className={styles.field}>
        <label className={styles.fieldLabel} htmlFor="results-student-id">
          Student ID
        </label>
        <input
          id="results-student-id"
          className={styles.textInput}
          type="text"
          value={studentId}
          onChange={(e) => onStudentIdChange(e.target.value)}
          placeholder="e.g. guest_student"
        />
      </div>

      <div className={styles.field}>
        <label className={styles.fieldLabel} htmlFor="results-topic">
          Topic
        </label>
        {topicsError ? (
          <p className={styles.helperText}>{topicsError}</p>
        ) : (
          <select
            id="results-topic"
            className={styles.select}
            value={topicId}
            onChange={(e) => onTopicIdChange(e.target.value)}
            disabled={topicsLoading || topics.length === 0}
          >
            <option value="" disabled>
              {topicsLoading ? "Loading topics…" : "Choose a topic"}
            </option>
            {topics.map((t) => (
              <option key={t.topic_id} value={t.topic_id}>
                {t.name} ({t.n_questions} questions)
              </option>
            ))}
          </select>
        )}
      </div>

      <div className={styles.buttonRow}>
        <button
          className={styles.primaryButton}
          onClick={onView}
          disabled={!canView}
        >
          View results
        </button>
        <span className={styles.divider}>or</span>
        <button className={styles.secondaryButton} onClick={onSample}>
          See a sample result
        </button>
      </div>
    </div>
  );
}

function ResultsDashboard({ payload }: { payload: DashboardPayload }) {
  const { total_attempts, accuracy_pct, chart_data, weak_point_info } =
    payload;

  return (
    <div className={styles.dashboard}>
      <div className={styles.statRow}>
        <div className={styles.statCard}>
          <div className={styles.statValue}>{accuracy_pct}%</div>
          <div className={styles.statLabel}>Accuracy</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statValue}>{total_attempts}</div>
          <div className={styles.statLabel}>Total attempts</div>
        </div>
      </div>

      {/* The diagnosis leads — it's the answer to the question this whole
          page exists to ask. The breakdown and remedial pathway below are
          the evidence and the plan, not co-equal headlines. */}
      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Weak point diagnosis</h2>
        <WeakPointCallout info={weak_point_info} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionHeading}>Wrong answers by category</h2>
        <div className={styles.sectionCard}>
          <ErrorBreakdown chartData={chart_data} />
        </div>
      </section>

      {(weak_point_info.remedial_note ||
        (weak_point_info.selected_questions &&
          weak_point_info.selected_questions.length > 0)) && (
        <section className={styles.section}>
          <h2 className={styles.sectionHeading}>Remedial pathway</h2>
          <div className={styles.sectionCard}>
            {weak_point_info.remedial_note && (
              <div className={styles.remedialNote}>
                {weak_point_info.remedial_note}
              </div>
            )}
            <QueueList questions={weak_point_info.selected_questions ?? []} />
          </div>
        </section>
      )}
    </div>
  );
}

function ErrorBreakdown({ chartData }: { chartData: ChartDatum[] }) {
  const total = chartData.reduce((s, d) => s + d.value, 0);

  if (chartData.length === 0 || total === 0) {
    return (
      <p className={styles.emptyState}>
        No categorized wrong answers yet — the breakdown fills in once this
        student has missed a few questions.
      </p>
    );
  }

  const sorted = [...chartData].sort((a, b) => b.value - a.value);

  return (
    <div>
      {sorted.map((d, i) => {
        const pct = Math.round((d.value / total) * 100);
        const explicitColor = d.color;
        const fallbackClass =
          styles[PALETTE_CLASSES[i % PALETTE_CLASSES.length]];
        const swatchStyle = explicitColor
          ? { background: explicitColor }
          : undefined;
        const fillStyle = explicitColor
          ? { width: `${pct}%`, background: explicitColor }
          : { width: `${pct}%` };
        return (
          <div className={styles.barRow} key={d.category ?? d.label}>
            <div className={styles.barLabel} title={d.label}>
              <span
                className={`${styles.barSwatch} ${
                  explicitColor ? "" : fallbackClass
                }`}
                style={swatchStyle}
                aria-hidden="true"
              />
              <span className={styles.barLabelText}>{d.label}</span>
            </div>
            <div className={styles.barTrack}>
              <div
                className={`${styles.barFill} ${
                  explicitColor ? "" : fallbackClass
                }`}
                style={fillStyle}
              />
            </div>
            <div className={styles.barPct}>{pct}%</div>
          </div>
        );
      })}
    </div>
  );
}

function WeakPointCallout({
  info,
}: {
  info: DashboardPayload["weak_point_info"];
}) {
  const meta = STATUS_META[info.status];
  const toneClassName = styles[toneClass[meta.tone]];

  const formattedCategory = info.dominant_category
    ? info.dominant_category.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : null;

  const sharePct =
    info.share_of_errors !== null && info.share_of_errors !== undefined
      ? Math.round(info.share_of_errors * 100)
      : null;

  let heading = meta.fallbackHeading;
  let body = info.message ?? "";

  switch (info.status) {
    case "no_signal":
      heading = "Not enough data yet";
      body =
        info.message ??
        "This student hasn't missed enough questions on this topic to say anything about a pattern.";
      break;
    case "provisional":
      heading = formattedCategory
        ? `Leaning toward: ${formattedCategory}`
        : "A pattern may be emerging";
      body =
        (sharePct !== null
          ? `${sharePct}% of wrong answers so far trace to this category, `
          : "") +
        "but the topic hasn't hit the confidence gate yet — this could shift as more questions are answered.";
      break;
    case "no_clear_pattern":
      heading = "No single category dominates";
      body =
        info.message ??
        "Enough attempts are in to trust the data, but the errors are spread fairly evenly across categories — no one fallacy stands out yet.";
      break;
    case "confident":
      heading = formattedCategory
        ? `Dominant weak point: ${formattedCategory}`
        : "Dominant weak point identified";
      body =
        (sharePct !== null
          ? `${sharePct}% of wrong answers on this topic trace to this category. `
          : "") + "The confidence gate has been met.";
      break;
  }

  return (
    <div className={`${styles.callout} ${toneClassName}`}>
      <span className={styles.calloutTone}>{meta.badge}</span>
      <h3 className={styles.calloutCat}>{heading}</h3>
      <p className={styles.calloutBody}>{body}</p>
    </div>
  );
}

function QueueList({ questions }: { questions: { stem: string }[] }) {
  if (questions.length === 0) {
    return (
      <p className={styles.emptyState}>No specific questions queued yet.</p>
    );
  }

  return (
    <div>
      {questions.map((q, idx) => (
        <div className={styles.queueItem} key={idx}>
          <div className={styles.queueNum}>
            {String(idx + 1).padStart(2, "0")}
          </div>
          <div className={styles.queueStem}>{q.stem}</div>
        </div>
      ))}
    </div>
  );
}