"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import styles from "./page.module.css";
import {
  ApiError,
  AnswerResponse,
  QuizQuestion,
  Topic,
  fetchNextQuestion,
  fetchTopics,
  submitAnswer,
} from "@/lib/api";

type Phase =
  | "setup" // choosing student id / topic, quiz not started
  | "loading" // fetching the next question
  | "question" // question shown, awaiting a click
  | "submitting" // answer sent, awaiting the server's verdict
  | "answered" // feedback shown for the current question
  | "done" // no unattempted questions left
  | "error"; // something went wrong

const OPTION_LETTERS = ["A", "B", "C", "D"];

export default function QuizPage() {
  // --- topic list -------------------------------------------------------
  const [topics, setTopics] = useState<Topic[]>([]);
  const [topicsError, setTopicsError] = useState<string | null>(null);
  const [topicsLoading, setTopicsLoading] = useState(true);

  // --- session (student + topic in play) --------------------------------
  const [studentId, setStudentId] = useState("");
  const [topicId, setTopicId] = useState("");

  // --- quiz state ---------------------------------------------------------
  const [phase, setPhase] = useState<Phase>("setup");
  const [question, setQuestion] = useState<QuizQuestion | null>(null);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<AnswerResponse | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // score, session-local only (not fetched from the API)
  const [sessionCorrect, setSessionCorrect] = useState(0);
  const [sessionAttempted, setSessionAttempted] = useState(0);

  const questionStartRef = useRef<number | null>(null);

  // --- load topics on mount ----------------------------------------------
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
        setTopicsError(err instanceof ApiError ? err.message : "Couldn't load topics.");
      })
      .finally(() => {
        if (!cancelled) setTopicsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // --- live elapsed-time display while a question is on screen -----------
  useEffect(() => {
    if (phase !== "question") return;
    const id = setInterval(() => {
      if (questionStartRef.current !== null) {
        setElapsedSec((performance.now() - questionStartRef.current) / 1000);
      }
    }, 200);
    return () => clearInterval(id);
  }, [phase, question?.question_id]);

  // --- data flow -----------------------------------------------------------
  const loadNextQuestion = useCallback(async (sid: string, tid: string) => {
    setPhase("loading");
    setSelectedOptionId(null);
    setFeedback(null);
    setErrorMessage(null);

    try {
      const data = await fetchNextQuestion(sid, tid);
      if (!data.question) {
        setQuestion(null);
        setRemaining(0);
        setPhase("done");
        return;
      }
      setQuestion(data.question);
      setRemaining(data.remaining);
      questionStartRef.current = performance.now();
      setElapsedSec(0);
      setPhase("question");
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Couldn't load the next question.");
      setPhase("error");
    }
  }, []);

  const handleStart = () => {
    const sid = studentId.trim();
    if (!sid || !topicId) return;
    setSessionCorrect(0);
    setSessionAttempted(0);
    void loadNextQuestion(sid, topicId);
  };

  const handleSelectOption = async (optionId: string) => {
    if (phase !== "question" || !question) return;

    const elapsed = questionStartRef.current
      ? (performance.now() - questionStartRef.current) / 1000
      : 0;

    setSelectedOptionId(optionId);
    setPhase("submitting");

    try {
      const result = await submitAnswer({
        student_id: studentId.trim(),
        topic_id: topicId,
        question_id: question.question_id,
        option_id: optionId,
        time_taken_sec: elapsed,
      });
      setFeedback(result);
      setSessionAttempted((n) => n + 1);
      if (result.is_correct) setSessionCorrect((n) => n + 1);
      setPhase("answered");
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Couldn't submit that answer.");
      setPhase("error");
    }
  };

  const handleNext = () => {
    void loadNextQuestion(studentId.trim(), topicId);
  };

  const handleChangeSession = () => {
    setPhase("setup");
    setQuestion(null);
    setFeedback(null);
    setSelectedOptionId(null);
    setErrorMessage(null);
  };

  const handleRetry = () => {
    if (studentId.trim() && topicId) {
      void loadNextQuestion(studentId.trim(), topicId);
    } else {
      setPhase("setup");
    }
  };

  const inSession = phase !== "setup";

  return (
    <div className={styles.page}>
      <header className={styles.intro}>
        <h1 className={styles.title}>Practice quiz</h1>
        <p className={styles.subtitle}>
          Each wrong option is tagged with the kind of mistake it represents,
          so your results later show why you missed it, not just that you
          did.
        </p>
      </header>

      {inSession && (
        <div className={styles.sessionBar}>
          <div className={styles.sessionInfo}>
            <strong>{studentId}</strong> · {topicId}
            {sessionAttempted > 0 && (
              <span className={styles.sessionScore}>
                {" "}
                — {sessionCorrect}/{sessionAttempted} correct this session
              </span>
            )}
          </div>
          <button className={styles.secondaryButton} onClick={handleChangeSession}>
            Change student or topic
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
          onStart={handleStart}
        />
      )}

      {phase === "loading" && (
        <p className={styles.skeleton} aria-live="polite">
          Loading question…
        </p>
      )}

      {(phase === "question" || phase === "submitting" || phase === "answered") && question && (
        <section className={styles.questionCard} key={question.question_id}>
          <div className={styles.metaRow}>
            <span className={styles.metaTag}>difficulty {question.difficulty}</span>
            {remaining !== null && (
              <span className={styles.metaTag}>
                {remaining} question{remaining === 1 ? "" : "s"} queued
              </span>
            )}
            {phase === "question" && (
              <span className={styles.timer}>{elapsedSec.toFixed(1)}s</span>
            )}
          </div>

          <h2 className={styles.stem}>{question.stem}</h2>

          <ul className={styles.options}>
            {question.options.map((option, i) => (
              <li key={option.option_id}>
                <OptionButton
                  letter={OPTION_LETTERS[i] ?? String(i + 1)}
                  text={option.option_text}
                  disabled={phase !== "question"}
                  state={optionState(option.option_id, phase, selectedOptionId, feedback)}
                  onClick={() => handleSelectOption(option.option_id)}
                />
              </li>
            ))}
          </ul>

          {phase === "answered" && feedback && (
            <div
              className={`${styles.feedbackBanner} ${
                feedback.is_correct ? styles.feedbackCorrect : styles.feedbackIncorrect
              }`}
              role="status"
              aria-live="polite"
            >
              <span className={styles.feedbackVerdict}>
                <span className={styles.feedbackDot} aria-hidden="true" />
                {feedback.is_correct ? "Correct" : "Not quite"}
              </span>
              <button className={styles.primaryButton} onClick={handleNext}>
                Next question
              </button>
            </div>
          )}
        </section>
      )}

      {phase === "done" && (
        <div className={styles.statusCard}>
          <DoneMark />
          <h2 className={styles.statusHeading}>No more questions</h2>
          <p className={styles.statusBody}>
            {studentId} has answered every available question in {topicId} for now.
          </p>
          <button className={styles.secondaryButton} onClick={handleChangeSession}>
            Pick a different topic
          </button>
        </div>
      )}

      {phase === "error" && (
        <div className={`${styles.statusCard} ${styles.errorCard}`} role="alert">
          <ErrorMark />
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
  onStart,
}: {
  studentId: string;
  onStudentIdChange: (v: string) => void;
  topicId: string;
  onTopicIdChange: (v: string) => void;
  topics: Topic[];
  topicsLoading: boolean;
  topicsError: string | null;
  onStart: () => void;
}) {
  const canStart = studentId.trim().length > 0 && topicId.length > 0;

  return (
    <div className={styles.setupCard}>
      <div className={styles.field}>
        <label className={styles.fieldLabel} htmlFor="student-id">
          Student ID
        </label>
        <input
          id="student-id"
          className={styles.textInput}
          type="text"
          value={studentId}
          onChange={(e) => onStudentIdChange(e.target.value)}
          placeholder="e.g. guest_student"
        />
      </div>

      <div className={styles.field}>
        <label className={styles.fieldLabel} htmlFor="topic">
          Topic
        </label>
        {topicsError ? (
          <p className={styles.helperText}>{topicsError}</p>
        ) : (
          <select
            id="topic"
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

      <button className={styles.primaryButton} onClick={onStart} disabled={!canStart}>
        Start quiz
      </button>
    </div>
  );
}

type OptionState = "default" | "selected" | "correct" | "incorrect" | "muted";

function optionState(
  optionId: string,
  phase: Phase,
  selectedOptionId: string | null,
  feedback: AnswerResponse | null
): OptionState {
  if (phase === "submitting") {
    return optionId === selectedOptionId ? "selected" : "muted";
  }
  if (phase === "answered" && feedback) {
    if (optionId === feedback.correct_option_id) return "correct";
    if (optionId === selectedOptionId) return "incorrect";
    return "muted";
  }
  return "default";
}

function OptionButton({
  letter,
  text,
  disabled,
  state,
  onClick,
}: {
  letter: string;
  text: string;
  disabled: boolean;
  state: OptionState;
  onClick: () => void;
}) {
  const rowClass =
    state === "selected"
      ? styles.optionButtonSelected
      : state === "correct"
      ? styles.optionButtonCorrect
      : state === "incorrect"
      ? styles.optionButtonIncorrect
      : state === "muted"
      ? styles.optionButtonMuted
      : "";

  const markClass =
    state === "selected"
      ? styles.markSelected
      : state === "correct"
      ? styles.markCorrect
      : state === "incorrect"
      ? styles.markIncorrect
      : "";

  return (
    <button
      type="button"
      className={`${styles.optionButton} ${rowClass}`}
      disabled={disabled}
      onClick={onClick}
    >
      <span className={`${styles.mark} ${markClass}`} aria-hidden="true">
        {state === "correct" ? (
          <CheckIcon />
        ) : state === "incorrect" ? (
          <CrossIcon />
        ) : (
          letter
        )}
      </span>
      <span className={styles.optionText}>{text}</span>
      {state === "correct" && <span className={styles.srOnly}>Correct answer</span>}
      {state === "incorrect" && <span className={styles.srOnly}>Your answer — incorrect</span>}
    </button>
  );
}

// --- small marks, drawn in the same thin-stroke language as the header logo ---

function CheckIcon() {
  return (
    <svg className={styles.markIcon} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M3.5 8.5 6.5 11.5 12.5 4.5"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CrossIcon() {
  return (
    <svg className={styles.markIcon} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M4 4l8 8M12 4l-8 8"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

function DoneMark() {
  return (
    <svg className={styles.statusMark} viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <circle cx="20" cy="20" r="15" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M13.5 20.5 18 25 27 15"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ErrorMark() {
  return (
    <svg className={styles.statusMark} viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <circle cx="20" cy="20" r="15" stroke="currentColor" strokeWidth="1.4" />
      <path d="M20 13v10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="20" cy="27.5" r="1.1" fill="currentColor" />
    </svg>
  );
}
