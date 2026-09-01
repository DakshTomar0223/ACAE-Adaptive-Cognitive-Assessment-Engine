"""
Weak-Point Isolator — Phase 3 of ACAE[cite: 10].

Given a student's cognitive profile (from cognitive_profiler.py), selects
the next questions to serve: ones whose distractor set is heaviest in the
student's dominant error category[cite: 10].
"""
import argparse
import sqlite3
import json
from cognitive_profiler import (
    build_profile,
    other_topics_correct_avg,
    MIN_ATTEMPTS_FOR_CONFIDENCE,
)
from remedial_engine import get_remedial_plan, get_remedial_note


def _select_example_questions(db_path, topic_id, category, student_id, n):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT q.question_id, q.stem
        FROM questions q
        JOIN options o ON o.question_id = q.question_id
        WHERE q.topic_id = ? AND o.error_category = ?
        AND q.question_id NOT IN (
            SELECT question_id FROM attempts WHERE student_id = ?
        )
        LIMIT ?
        """,
        (topic_id, category, student_id, n),
    )
    fresh = cur.fetchall()
    if fresh:
        conn.close()
        return [{"question_id": qid, "stem": stem} for qid, stem in fresh], "fresh"

    cur.execute(
        """
        SELECT DISTINCT q.question_id, q.stem
        FROM questions q
        JOIN options o ON o.question_id = q.question_id
        WHERE q.topic_id = ? AND o.error_category = ?
        LIMIT ?
        """,
        (topic_id, category, n),
    )
    repeat = cur.fetchall()
    conn.close()
    if repeat:
        return [{"question_id": qid, "stem": stem} for qid, stem in repeat], "repeated"

    return [], "none_available"


def _timing_flags_payload(profile, baseline):
    return [
        {
            "category": name,
            "detail": detail,
            "remedial_note": get_remedial_note(name),
            "remedial_plan": get_remedial_plan(name),
        }
        for name, detail in profile.timing_flags(baseline)
    ]


def select_next_questions(db_path: str, student_id: str, topic_id: str, n: int = 3):
    profiles = build_profile(db_path, student_id)
    profile = profiles.get(topic_id)

    if not profile:
        return {
            "status": "no_signal",
            "message": "No attempts logged for this topic yet — serve general practice.",
            "timing_flags": [],
        }

    baseline = other_topics_correct_avg(profiles, topic_id)
    timing_flags = _timing_flags_payload(profile, baseline)

    if not profile.category_votes:
        return {
            "status": "no_signal",
            "message": "No error-category signal yet — serve general practice.",
            "timing_flags": timing_flags,
        }

    dominant_cat, share = profile.dominant_category

    if dominant_cat is None:
        return {
            "status": "no_clear_pattern",
            "message": (
                "Wrong answers so far look like isolated slips rather than "
                "a systematic pattern — serve general practice."
            ),
            "timing_flags": timing_flags,
        }

    if not profile.is_confident:
        return {
            "status": "provisional",
            "message": (
                f"Only {profile.total_attempts}/{MIN_ATTEMPTS_FOR_CONFIDENCE} attempts logged — "
                f"provisional signal points to '{dominant_cat}' but not yet confident."
            ),
            "provisional_category": dominant_cat,
            "timing_flags": timing_flags,
        }

    selected, selection_note = _select_example_questions(
        db_path, topic_id, dominant_cat, student_id, n
    )

    remedial_plan = get_remedial_plan(dominant_cat)

    result = {
        "status": "confident",
        "dominant_category": dominant_cat,
        "share_of_errors": round(share, 2),
        "selected_questions": selected,
        "selection_note": selection_note,
        "remedial_note": remedial_plan["summary_note"],
        "remedial_plan": remedial_plan,
        "timing_flags": timing_flags,
    }
    if selection_note == "none_available":
        result["message"] = (
            f"No example questions currently exist for '{dominant_cat}' in "
            f"this topic (likely deleted/edited since the attempt was logged) "
            "— falling back to remedial note only."
        )
    return result


def get_default_context(db_path: str):
    """Queries DB for an available student_id and topic_id combination."""
    student_id, topic_id = "student_01", "kinematics_1d"
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT a.student_id, q.topic_id
            FROM attempts a
            JOIN questions q ON a.question_id = q.question_id
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row:
            if row[0]:
                student_id = row[0]
            if row[1]:
                topic_id = row[1]
        else:
            cur.execute("SELECT topic_id FROM questions LIMIT 1")
            t_row = cur.fetchone()
            if t_row and t_row[0]:
                topic_id = t_row[0]
        conn.close()
    except Exception:
        pass
    return student_id, topic_id


def main():
    parser = argparse.ArgumentParser(description="ACAE weak-point question selector")
    parser.add_argument("student_id", nargs="?", default=None, help="Student ID (optional)")
    parser.add_argument("topic_id", nargs="?", default=None, help="Topic ID (optional)")
    parser.add_argument("-n", type=int, default=3, help="Number of questions to select (default: 3)")
    parser.add_argument(
        "--db", default="acae.db", help="Path to the ACAE SQLite DB (default: acae.db)"
    )
    args = parser.parse_args()

    def_student, def_topic = get_default_context(args.db)
    student_id = args.student_id if args.student_id else def_student
    topic_id = args.topic_id if args.topic_id else def_topic

    if not args.student_id or not args.topic_id:
        print(f"[info] Defaulting parameters to student_id='{student_id}', topic_id='{topic_id}'")

    result = select_next_questions(args.db, student_id, topic_id, args.n)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()