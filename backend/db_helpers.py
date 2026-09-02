"""
db_helpers.py — shared SQLite access helpers for ACAE.

Extracted verbatim from app.py's Phase 5B implementation so that both the
Streamlit app (app.py) and the Flask API (api.py) call the exact same
quiz/attempt-logging logic instead of each defining their own copy.
app.py can't be imported directly for this purpose — it runs Streamlit UI
code (st.set_page_config, sidebar widgets, etc.) at module level, which
only works inside a `streamlit run` process.
"""

import sqlite3
from datetime import datetime, timezone

DB_PATH = "acae.db"
DEFAULT_TOPIC_ID = "phys_kinematics_2d"


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_student_exists(conn: sqlite3.Connection, student_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO students (student_id, name) VALUES (?, ?)",
            (student_id, None),
        )
        conn.commit()


def fetch_all_topics(conn: sqlite3.Connection):
    rows = conn.execute(
        """
        SELECT t.topic_id, t.name, COUNT(q.question_id) AS n_questions
        FROM topics t
        LEFT JOIN questions q ON q.topic_id = t.topic_id
        GROUP BY t.topic_id
        ORDER BY t.topic_id ASC
        """
    ).fetchall()
    return rows


def get_default_topic_id(conn: sqlite3.Connection) -> str:
    """Falls back to whichever topic has the most questions, then to the
    hardcoded default — mirrors run_quiz.py's get_default_topic_id()."""
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
    return conn.execute(
        """
        SELECT option_id, option_text, is_correct
        FROM options
        WHERE question_id = ?
        ORDER BY option_id ASC
        """,
        (question_id,),
    ).fetchall()


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
