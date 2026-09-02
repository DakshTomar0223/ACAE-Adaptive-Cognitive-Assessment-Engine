#!/usr/bin/env python3
"""
app.py - ACAE Streamlit app (Phase 5B: quiz-taking + results screen)

Browser-based replacement for run_quiz.py's terminal loop. Lets a student
pick (or accept a default) student_id + topic_id, answers unattempted
questions one at a time, and logs each attempt to the same `attempts`
table run_quiz.py already uses — same schema, same log_attempt() logic,
just triggered from a Streamlit button instead of stdin.

Phase 5B adds a "My Results" tab that calls cognitive_profiler.build_profile()
and weak_point_selector.select_next_questions() directly (no shelling out,
no JSON export file) to show accuracy, the error-category breakdown, the
dominant weak point (or an honest "not enough data" / "no clear pattern"
message), the remedial plan, and the next recommended questions. Both tabs
are re-executed on every Streamlit rerun, so Results reflects the latest
attempt immediately after Submit — no manual page reload needed.

Run with:
    streamlit run app.py
"""

import time

import streamlit as st

from cognitive_profiler import build_profile, other_topics_correct_avg, MIN_ATTEMPTS_FOR_CONFIDENCE
from weak_point_selector import select_next_questions

# Phase 5C: reuse seed_and_simulate.py's QUESTIONS + simulate_attempts()
# wholesale for the "See a sample result" demo — no re-implementing the
# biased-student simulation here.
import seed_and_simulate as sample_data

# Phase 6A: DB access helpers (get_connection, ensure_student_exists,
# fetch_all_topics, get_default_topic_id, fetch_unattempted_questions,
# fetch_options, log_attempt) now live in db_helpers.py so api.py can
# reuse the exact same logic without importing this Streamlit module.
from db_helpers import (
    DB_PATH,
    get_connection,
    ensure_student_exists,
    fetch_all_topics,
    get_default_topic_id,
    fetch_unattempted_questions,
    fetch_options,
    log_attempt,
)

VALID_CHOICES = ("A", "B", "C", "D")
DEFAULT_STUDENT_ID = "guest_student"
DEFAULT_TOPIC_ID = "phys_kinematics_2d"

# Demo/"sample result" config — always a distinct file from the real DB_PATH
# above, so clicking the sample button can never touch real attempt data.
# sample_data.DB_PATH is resolved relative to seed_and_simulate.py's own
# location, so this stays correct regardless of app.py's working directory.
DEMO_DB_PATH = sample_data.DB_PATH
DEMO_STUDENT_ID = sample_data.STUDENT_ID
DEMO_TOPIC_ID = sample_data.QUESTIONS[0]["topic"]


def render_results(
    student_id: str, topic_id: str, db_path: str = DB_PATH, is_demo: bool = False
) -> bool:
    """Results screen (Phase 5B): profile + weak-point/remedial plan, built
    straight from cognitive_profiler.build_profile() and
    weak_point_selector.select_next_questions() — no shelling out, no JSON
    export file, just direct Python calls against the live DB.

    db_path lets this render either the real acae.db or the sample/demo DB
    (Phase 5C) with identical logic. Returns True if there was a profile to
    show, False if there were zero attempts — callers use that to decide
    whether to offer the "See a sample result" button.
    """

    if is_demo:
        st.subheader(f"🧪 Sample Results — {student_id} · {topic_id}")
    else:
        st.subheader(f"Results — {student_id} · {topic_id}")

    profiles = build_profile(db_path, student_id)
    profile = profiles.get(topic_id)

    if profile is None or profile.total_attempts == 0:
        st.info("No attempts logged for this topic yet — serve general practice.")
        return False

    # --- attempts / accuracy -------------------------------------------
    col1, col2 = st.columns(2)
    col1.metric("Total attempts", profile.total_attempts)
    col2.metric("Accuracy", f"{profile.accuracy:.0%}")
    st.progress(profile.accuracy)

    # --- error category breakdown ---------------------------------------
    st.markdown("##### Wrong answers by error category")
    if profile.category_votes:
        total_wrong = sum(profile.category_votes.values())
        for cat, votes in sorted(
            profile.category_votes.items(), key=lambda kv: (-kv[1], kv[0])
        ):
            label = cat.replace("_", " ").title()
            share = votes / total_wrong
            st.write(f"**{label}** — {votes}/{total_wrong} wrong answers ({share:.0%})")
            st.progress(share)
    else:
        st.caption(
            "No error-category signal yet (all correct so far, or no tagged "
            "wrong answers)."
        )

    st.divider()

    # --- dominant weak point + remedial plan (delegates the confidence
    # gate / status logic entirely to select_next_questions, so the
    # messages shown here always match what that function decided) -------
    result = select_next_questions(db_path, student_id, topic_id)
    status = result["status"]

    st.markdown("##### Weak-point diagnosis")
    if status == "no_signal":
        st.info(result["message"])
    elif status == "no_clear_pattern":
        st.warning(result["message"])
    elif status == "provisional":
        st.warning(result["message"])
    elif status == "confident":
        cat_label = result["dominant_category"].replace("_", " ").title()
        st.error(
            f"**Dominant weak point: {cat_label}** — "
            f"{result['share_of_errors']:.0%} of wrong answers on this topic "
            f"(confidence gate met, {MIN_ATTEMPTS_FOR_CONFIDENCE}+ attempts)"
        )

        st.markdown("**Remedial note**")
        st.write(result["remedial_note"])

        drill_sequence = result["remedial_plan"].get("drill_sequence", [])
        if drill_sequence:
            st.markdown("**Drill sequence**")
            for step in drill_sequence:
                st.write(step)

        st.markdown("**Next recommended questions**")
        selected = result.get("selected_questions", [])
        if selected:
            for i, sq in enumerate(selected, start=1):
                st.write(f"{i}. [{sq['question_id']}] {sq['stem']}")
            if result.get("selection_note") == "repeated":
                st.caption(
                    "No fresh unattempted questions in this category — "
                    "showing previously-seen ones instead."
                )
        else:
            st.caption(
                result.get("message")
                or "No example questions currently available for this category."
            )
    else:
        # Defensive fallback in case select_next_questions ever returns an
        # unrecognized status — surface it rather than silently hiding it.
        st.warning(result.get("message", f"Unrecognized status: {status}"))

    # --- timing flags (bonus signal from cognitive_profiler) ------------
    timing_flags = result.get("timing_flags", [])
    if timing_flags:
        st.divider()
        st.markdown("##### Timing flags")
        for flag in timing_flags:
            flag_label = flag["category"].replace("_", " ").title()
            st.write(f"⏱️ **{flag_label}** — {flag['detail']}")
            st.caption(flag["remedial_note"])

    return True


# --------------------------------------------------------------------------
# Streamlit app
# --------------------------------------------------------------------------

st.set_page_config(page_title="ACAE — Quiz", page_icon="🧠", layout="centered")

conn = get_connection()

# --- session state -----------------------------------------------------
# question_start_time: wall-clock time (time.monotonic()) the current
#   question was first shown, used to compute time_taken_sec on submit.
# session_correct / session_attempted: running tally for this browser
#   session only (not a DB query) so the "session done" summary is cheap.
if "question_start_time" not in st.session_state:
    st.session_state.question_start_time = None
if "session_correct" not in st.session_state:
    st.session_state.session_correct = 0
if "session_attempted" not in st.session_state:
    st.session_state.session_attempted = 0
if "last_result" not in st.session_state:
    st.session_state.last_result = None  # (is_correct, elapsed) or None
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "real"  # "real" or "demo" (Phase 5C sample result)
if "demo_db_ready" not in st.session_state:
    st.session_state.demo_db_ready = False

st.title("🧠 ACAE — Quiz")

# --- student_id + topic_id picker --------------------------------------
with st.sidebar:
    st.header("Session")
    student_id_input = st.text_input(
        "Student ID",
        value=st.session_state.get("student_id", DEFAULT_STUDENT_ID),
        help="Type any name/ID. Defaults to 'guest_student' if left as-is.",
    )

    topics = fetch_all_topics(conn)
    topic_ids = [t["topic_id"] for t in topics]
    topic_labels = {
        t["topic_id"]: f"{t['topic_id']}  ({t['n_questions']} questions)"
        for t in topics
    }

    if not topic_ids:
        st.error(
            "No topics found in the database. Run `python load_questions.py` "
            "first to load the question bank."
        )
        st.stop()

    default_topic = st.session_state.get("topic_id") or get_default_topic_id(conn)
    default_index = topic_ids.index(default_topic) if default_topic in topic_ids else 0

    topic_id_input = st.selectbox(
        "Topic",
        options=topic_ids,
        index=default_index,
        format_func=lambda tid: topic_labels.get(tid, tid),
    )

    st.caption(f"Session score: {st.session_state.session_correct}/"
               f"{st.session_state.session_attempted} correct")

# Detect a student/topic change — reset the per-question timer so a stale
# start time from a previous question/topic doesn't leak into a new one.
student_id = (student_id_input or "").strip() or DEFAULT_STUDENT_ID
topic_id = topic_id_input

if (
    st.session_state.get("student_id") != student_id
    or st.session_state.get("topic_id") != topic_id
):
    st.session_state.student_id = student_id
    st.session_state.topic_id = topic_id
    st.session_state.question_start_time = None
    st.session_state.last_result = None
    # A real student/topic switch means "sample mode" no longer refers to
    # what's on screen — drop back to real data so it isn't left showing
    # demo results under a mismatched sidebar selection.
    st.session_state.view_mode = "real"

ensure_student_exists(conn, student_id)

# --------------------------------------------------------------------------
# Tabs. Streamlit re-executes the whole script (and therefore the content
# of BOTH tabs) on every rerun — including the st.rerun() fired right after
# an attempt is logged below — so the Results tab is always built from a
# fresh DB read. No caching, no manual "refresh" step needed.
# --------------------------------------------------------------------------
quiz_tab, results_tab = st.tabs(["🧠 Quiz", "📊 My Results"])

# --- Quiz tab --------------------------------------------------------------
with quiz_tab:
    questions = fetch_unattempted_questions(conn, student_id, topic_id)

    if st.session_state.last_result is not None:
        is_correct, elapsed = st.session_state.last_result
        if is_correct:
            st.success(f"Correct! ({elapsed:.1f}s)")
        else:
            st.error(f"Incorrect. ({elapsed:.1f}s)")
        st.session_state.last_result = None

    if not questions:
        st.info(
            f"No unattempted questions left for **{student_id}** in topic "
            f"**{topic_id}**. Pick a different topic from the sidebar, or use "
            f"a new student ID."
        )
        if st.session_state.session_attempted > 0:
            st.write(
                f"Session done: **{st.session_state.session_correct}/"
                f"{st.session_state.session_attempted}** correct."
            )
        st.caption("Check the **📊 My Results** tab above for your full breakdown.")
    else:
        q = questions[0]
        options = fetch_options(conn, q["question_id"])

        if len(options) != 4:
            st.warning(
                f"Question {q['question_id']} has {len(options)} options "
                "(expected 4) — skipping. Reload the page to see the next one."
            )
        else:
            if st.session_state.question_start_time is None:
                st.session_state.question_start_time = time.monotonic()

            st.caption(
                f"{len(questions)} question(s) queued  ·  "
                f"[{q['question_id']}]  ·  difficulty {q['difficulty']}"
            )
            st.subheader(q["stem"])

            option_map = {
                label: opt for label, opt in zip(VALID_CHOICES, options)
            }
            choice_label = st.radio(
                "Choose an answer:",
                options=list(option_map.keys()),
                format_func=lambda label: f"{label}. {option_map[label]['option_text']}",
                index=None,
                key=f"choice_{student_id}_{topic_id}_{q['question_id']}",
            )

            submit = st.button("Submit", type="primary", disabled=(choice_label is None))

            if submit and choice_label is not None:
                elapsed = time.monotonic() - st.session_state.question_start_time
                chosen_option = option_map[choice_label]
                is_correct = int(chosen_option["is_correct"])

                log_attempt(
                    conn,
                    student_id,
                    q["question_id"],
                    chosen_option["option_id"],
                    is_correct,
                    elapsed,
                )

                st.session_state.session_attempted += 1
                if is_correct:
                    st.session_state.session_correct += 1

                st.session_state.last_result = (bool(is_correct), elapsed)
                st.session_state.question_start_time = None

                # Rerunning re-executes the whole script, which rebuilds the
                # Results tab below from the DB we just wrote to — that's
                # what keeps it "live" without a manual page reload.
                st.rerun()

    st.divider()
    st.caption("Want a breakdown of *why* you're missing questions? See the **📊 My Results** tab above.")

# --- Results tab -------------------------------------------------------
with results_tab:
    if st.session_state.view_mode == "demo":
        st.warning(
            "🧪 **You're viewing SAMPLE / DEMO data** — this is a synthetic "
            f"student (`{DEMO_STUDENT_ID}`) with a deliberately biased weak "
            f"point, not **{student_id}**'s real attempts. Stored separately "
            f"in `{DEMO_DB_PATH}`; your real data in `{DB_PATH}` is untouched."
        )
        if st.button("← Back to my real results"):
            st.session_state.view_mode = "real"
            st.rerun()
        st.divider()

        render_results(DEMO_STUDENT_ID, DEMO_TOPIC_ID, db_path=DEMO_DB_PATH, is_demo=True)

    else:
        has_data = render_results(student_id, topic_id)

        if not has_data:
            st.divider()
            st.caption(
                "Nothing to show yet for this student/topic — want to see "
                "what a fully diagnosed result looks like instead?"
            )
            if st.button("👀 See a sample result"):
                # Only (re)generate the demo DB once per browser session —
                # cheap to build, but no need to redo it on every rerun.
                if not st.session_state.demo_db_ready:
                    demo_conn = sample_data.build_db()
                    sample_data.simulate_attempts(demo_conn)
                    demo_conn.close()
                    st.session_state.demo_db_ready = True
                st.session_state.view_mode = "demo"
                st.rerun()