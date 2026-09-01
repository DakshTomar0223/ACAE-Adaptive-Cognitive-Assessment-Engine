#!/usr/bin/env python3
"""
run_quiz.py - ACAE terminal quiz runner

Usage:
    python run_quiz.py <student_id> <topic_id> [--db acae.db]

Pulls all questions in a topic that the given student has not yet
attempted, presents them one at a time (stem + 4 options), reads a
keyboard choice (A/B/C/D), times the response, and logs it into the
`attempts` table.
"""

import argparse
import sqlite3
import sys
import time
from datetime import datetime, timezone

VALID_CHOICES = ("A", "B", "C", "D")

DEFAULT_STUDENT_ID = "guest_student"
DEFAULT_TOPIC_ID = "phys_kinematics_2d"


def get_default_topic_id(conn: sqlite3.Connection) -> str:
    """Falls back to whichever topic has the most unattempted questions,
    then to any topic at all, then to the hardcoded default."""
    row = conn.execute(
        """
        SELECT q.topic_id, COUNT(*) AS n
        FROM questions q
        GROUP BY q.topic_id
        ORDER BY n DESC
        LIMIT 1
        """
    ).fetchone()
    if row and row["topic_id"]:
        return row["topic_id"]
    return DEFAULT_TOPIC_ID


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_student_exists(conn: sqlite3.Connection, student_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
    ).fetchone()
    if row is None:
        # Auto-create so the loop doesn't hard-fail on a fresh student_id.
        conn.execute(
            "INSERT INTO students (student_id, name) VALUES (?, ?)",
            (student_id, None),
        )
        conn.commit()
        print(f"[info] student '{student_id}' not found — created new record.")


def fetch_unattempted_questions(
    conn: sqlite3.Connection, student_id: str, topic_id: str
):
    query = """
        SELECT q.question_id, q.stem, q.difficulty
        FROM questions q
        WHERE q.topic_id = ?
          AND q.question_id NOT IN (
              SELECT a.question_id
              FROM attempts a
              WHERE a.student_id = ?
          )
        ORDER BY q.difficulty ASC, q.question_id ASC
    """
    return conn.execute(query, (topic_id, student_id)).fetchall()


def fetch_options(conn: sqlite3.Connection, question_id: str):
    rows = conn.execute(
        """
        SELECT option_id, option_text, is_correct
        FROM options
        WHERE question_id = ?
        ORDER BY option_id ASC
        """,
        (question_id,),
    ).fetchall()
    if len(rows) != 4:
        print(
            f"[warn] question {question_id} has {len(rows)} options "
            "(expected 4) — skipping.",
            file=sys.stderr,
        )
    return rows


def prompt_choice() -> str:
    while True:
        raw = input("Your answer (A/B/C/D, or Q to quit): ").strip().upper()
        if raw == "Q":
            return "Q"
        if raw in VALID_CHOICES:
            return raw
        print("  Please enter A, B, C, D, or Q.")


def log_attempt(
    conn: sqlite3.Connection,
    student_id: str,
    question_id: str,
    chosen_option_id: str,
    is_correct: int,
    time_taken_sec: float,
) -> None:
    conn.execute(
        """
        INSERT INTO attempts
            (student_id, question_id, chosen_option_id, is_correct,
             time_taken_sec, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            question_id,
            chosen_option_id,
            is_correct,
            round(time_taken_sec, 2),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def run_quiz(db_path: str, student_id: str, topic_id: str) -> None:
    conn = get_connection(db_path)
    ensure_student_exists(conn, student_id)

    questions = fetch_unattempted_questions(conn, student_id, topic_id)
    if not questions:
        print(f"No unattempted questions for '{student_id}' in topic '{topic_id}'.")
        conn.close()
        return

    print(f"\n{len(questions)} question(s) queued for '{student_id}' "
          f"in topic '{topic_id}'.\n")

    correct_count = 0
    attempted_count = 0

    for q in questions:
        options = fetch_options(conn, q["question_id"])
        if len(options) != 4:
            continue  # already warned in fetch_options

        print("-" * 60)
        print(f"[{q['question_id']}] (difficulty {q['difficulty']})")
        print(q["stem"])
        print()
        for label, opt in zip(VALID_CHOICES, options):
            print(f"  {label}. {opt['option_text']}")
        print()

        start = time.monotonic()
        choice = prompt_choice()
        elapsed = time.monotonic() - start

        if choice == "Q":
            print("\nQuitting quiz early.")
            break

        chosen_option = options[VALID_CHOICES.index(choice)]
        is_correct = int(chosen_option["is_correct"])

        log_attempt(
            conn,
            student_id,
            q["question_id"],
            chosen_option["option_id"],
            is_correct,
            elapsed,
        )

        attempted_count += 1
        if is_correct:
            correct_count += 1
            print(f"Correct! ({elapsed:.1f}s)\n")
        else:
            print(f"Incorrect. ({elapsed:.1f}s)\n")

    print("-" * 60)
    print(f"Session done: {correct_count}/{attempted_count} correct.")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="ACAE terminal quiz runner")
    parser.add_argument(
        "student_id",
        nargs="?",
        default=None,
        help=f"Student ID to run the quiz for (optional — defaults to '{DEFAULT_STUDENT_ID}')",
    )
    parser.add_argument(
        "topic_id",
        nargs="?",
        default=None,
        help="Topic ID to pull questions from (optional — defaults to the topic with the most questions)",
    )
    parser.add_argument(
        "--db", default="acae.db", help="Path to the ACAE SQLite DB (default: acae.db)"
    )
    args = parser.parse_args()

    student_id = args.student_id or DEFAULT_STUDENT_ID
    topic_id = args.topic_id

    try:
        if topic_id is None:
            conn = get_connection(args.db)
            topic_id = get_default_topic_id(conn)
            conn.close()
            print(f"[info] No topic_id provided. Defaulting to: '{topic_id}'")
        if args.student_id is None:
            print(f"[info] No student_id provided. Defaulting to: '{student_id}'")

        run_quiz(args.db, student_id, topic_id)
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)


if __name__ == "__main__":
    main()