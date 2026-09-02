#!/usr/bin/env python3
"""
api.py — ACAE Flask API (Phase 6A)

REST wrapper around the existing ACAE modules, for a decoupled frontend
(Phase 6B). Every route below is a thin adapter: it reads the request,
calls the same functions app.py / export_dashboard_data.py / cognitive_profiler.py
/ weak_point_selector.py / seed_and_simulate.py already use, and serializes
the result. No diagnostic, quiz-flow, or remedial logic is reimplemented here.

Run with:
    python api.py
"""

import sqlite3

from flask import Flask, jsonify, request
from flask_cors import CORS

from db_helpers import (
    DB_PATH,
    get_connection,
    ensure_student_exists,
    fetch_all_topics,
    fetch_unattempted_questions,
    fetch_options,
    log_attempt,
)
from cognitive_profiler import build_profile
from weak_point_selector import select_next_questions
from export_dashboard_data import build_dashboard_payload
import seed_and_simulate as sample_data

app = Flask(__name__)
CORS(app)  # dev: allow all origins — tighten before any real deployment

DEMO_DB_PATH = sample_data.DB_PATH
DEMO_STUDENT_ID = sample_data.STUDENT_ID
DEMO_TOPIC_ID = sample_data.QUESTIONS[0]["topic"]


# --------------------------------------------------------------------------
# GET /api/topics
# --------------------------------------------------------------------------
@app.route("/api/topics", methods=["GET"])
def get_topics():
    conn = get_connection(DB_PATH)
    try:
        rows = fetch_all_topics(conn)
    finally:
        conn.close()

    return jsonify(
        [
            {
                "topic_id": r["topic_id"],
                "name": r["name"],
                "n_questions": r["n_questions"],
            }
            for r in rows
        ]
    )


# --------------------------------------------------------------------------
# GET /api/quiz/next?student_id=&topic_id=
#
# Returns the next unattempted question's stem plus its 4 options as
# option_id + option_text ONLY. is_correct and error_category are
# deliberately excluded — this payload goes to an untrusted client before
# they've answered, so leaking either would let the client cheat or infer
# the answer from which distractor category is present.
# --------------------------------------------------------------------------
@app.route("/api/quiz/next", methods=["GET"])
def get_next_question():
    student_id = request.args.get("student_id")
    topic_id = request.args.get("topic_id")
    if not student_id or not topic_id:
        return jsonify({"error": "student_id and topic_id are required query params"}), 400

    conn = get_connection(DB_PATH)
    try:
        ensure_student_exists(conn, student_id)
        questions = fetch_unattempted_questions(conn, student_id, topic_id)

        if not questions:
            return jsonify(
                {
                    "question": None,
                    "remaining": 0,
                    "message": f"No unattempted questions left for '{student_id}' in topic '{topic_id}'.",
                }
            )

        q = questions[0]
        options = fetch_options(conn, q["question_id"])
        if len(options) != 4:
            return (
                jsonify(
                    {
                        "error": f"question {q['question_id']} has {len(options)} options (expected 4)",
                    }
                ),
                500,
            )

        return jsonify(
            {
                "question": {
                    "question_id": q["question_id"],
                    "stem": q["stem"],
                    "difficulty": q["difficulty"],
                    "options": [
                        {"option_id": o["option_id"], "option_text": o["option_text"]}
                        for o in options
                    ],
                },
                "remaining": len(questions),
            }
        )
    finally:
        conn.close()


# --------------------------------------------------------------------------
# POST /api/quiz/answer
# Body: {student_id, topic_id, question_id, option_id, time_taken_sec}
# --------------------------------------------------------------------------
@app.route("/api/quiz/answer", methods=["POST"])
def post_answer():
    body = request.get_json(silent=True) or {}
    student_id = body.get("student_id")
    question_id = body.get("question_id")
    option_id = body.get("option_id")
    time_taken_sec = body.get("time_taken_sec")

    missing = [
        k
        for k in ("student_id", "question_id", "option_id", "time_taken_sec")
        if body.get(k) is None
    ]
    if missing:
        return jsonify({"error": f"missing required field(s): {', '.join(missing)}"}), 400

    conn = get_connection(DB_PATH)
    try:
        ensure_student_exists(conn, student_id)

        row = conn.execute(
            """
            SELECT o.is_correct, q.correct_option_id
            FROM options o
            JOIN questions q ON q.question_id = o.question_id
            WHERE o.option_id = ? AND o.question_id = ?
            """,
            (option_id, question_id),
        ).fetchone()

        if row is None:
            return (
                jsonify({"error": f"option_id '{option_id}' not found for question_id '{question_id}'"}),
                404,
            )

        is_correct = int(row["is_correct"])
        correct_option_id = row["correct_option_id"]

        log_attempt(
            conn,
            student_id,
            question_id,
            option_id,
            is_correct,
            float(time_taken_sec),
        )

        return jsonify({"is_correct": bool(is_correct), "correct_option_id": correct_option_id})
    finally:
        conn.close()


# --------------------------------------------------------------------------
# GET /api/results?student_id=&topic_id=
# Same JSON shape export_dashboard_data.py writes to dashboard_data.json —
# built via the shared build_dashboard_payload(), not re-derived here.
# --------------------------------------------------------------------------
@app.route("/api/results", methods=["GET"])
def get_results():
    student_id = request.args.get("student_id")
    topic_id = request.args.get("topic_id")
    if not student_id or not topic_id:
        return jsonify({"error": "student_id and topic_id are required query params"}), 400

    payload = build_dashboard_payload(DB_PATH, student_id, topic_id)
    return jsonify(payload)


# --------------------------------------------------------------------------
# POST /api/sample/generate
# (Re)seeds acae_demo.db via seed_and_simulate.build_db() + simulate_attempts().
# --------------------------------------------------------------------------
@app.route("/api/sample/generate", methods=["POST"])
def post_generate_sample():
    conn = sample_data.build_db()
    sample_data.simulate_attempts(conn)
    conn.close()

    return jsonify(
        {
            "status": "ok",
            "message": f"Seeded {len(sample_data.QUESTIONS)} questions and simulated attempts for '{DEMO_STUDENT_ID}'.",
            "db_path": DEMO_DB_PATH,
            "student_id": DEMO_STUDENT_ID,
            "topic_id": DEMO_TOPIC_ID,
        }
    )


# --------------------------------------------------------------------------
# GET /api/results/sample
# Same as /api/results, pinned to the demo DB/student/topic.
# --------------------------------------------------------------------------
@app.route("/api/results/sample", methods=["GET"])
def get_results_sample():
    payload = build_dashboard_payload(DEMO_DB_PATH, DEMO_STUDENT_ID, DEMO_TOPIC_ID)
    return jsonify(payload)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
