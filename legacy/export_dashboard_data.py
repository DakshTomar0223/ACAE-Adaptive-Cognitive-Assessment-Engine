import argparse
import json
import sqlite3
from cognitive_profiler import build_profile
from weak_point_selector import select_next_questions, get_default_context

# Visual color mapping for cognitive fault categories
CATEGORY_COLORS = {
    "visualization_spatial": "#C1502E",
    "formula_misapplication": "#E3A23D",
    "procedural_error": "#4C9490",
    "conceptual_misunderstanding": "#9350A1",
    "conceptual_synthesis_failure": "#3B6998",
    "careless_attention_slip": "#6B551F",
    "calculation_speed_deficit": "#A87232",
    "time_pressure_collapse": "#803520",
}

CATEGORY_LABELS = {
    "visualization_spatial": "Visualization / Spatial",
    "formula_misapplication": "Formula Misapplication",
    "procedural_error": "Procedural Error",
    "conceptual_misunderstanding": "Conceptual Misunderstanding",
    "conceptual_synthesis_failure": "Conceptual Synthesis",
    "careless_attention_slip": "Careless / Attention Slip",
    "calculation_speed_deficit": "Calculation Speed Deficit",
    "time_pressure_collapse": "Time Pressure Collapse",
}


def export_dashboard_data(
    db_path: str, student_id: str, topic_id: str, output_path: str = "dashboard_data.json"
):
    # Retrieve cognitive profile & weak point selection
    profiles = build_profile(db_path, student_id)
    profile = profiles.get(topic_id)
    weak_point_info = select_next_questions(db_path, student_id, topic_id)

    total_attempts = profile.total_attempts if profile else 0
    correct_attempts = profile.correct if profile else 0
    accuracy_pct = (
        round((correct_attempts / total_attempts) * 100) if total_attempts > 0 else 0
    )

    # Format fault category distribution for the radial chart
    chart_data = []
    if profile and profile.category_votes:
        for cat, count in profile.category_votes.items():
            chart_data.append(
                {
                    "category": cat,
                    "label": CATEGORY_LABELS.get(cat, cat.replace("_", " ").title()),
                    "value": count,
                    "color": CATEGORY_COLORS.get(cat, "#4C9490"),
                }
            )

    payload = {
        "student_id": student_id,
        "topic_id": topic_id,
        "total_attempts": total_attempts,
        "accuracy_pct": accuracy_pct,
        "chart_data": chart_data,
        "weak_point_info": weak_point_info,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Successfully exported ACAE dashboard data to '{output_path}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export ACAE student profile data to JSON for dashboard visualization."
    )
    parser.add_argument(
        "student_id",
        nargs="?",
        default=None,
        help="Student ID (optional — defaults to a student with attempts on record)",
    )
    parser.add_argument(
        "topic_id",
        nargs="?",
        default=None,
        help="Topic ID (optional — defaults to that student's most-attempted topic)",
    )
    parser.add_argument(
        "--db", default="acae.db", help="Path to SQLite database (default: acae.db)"
    )
    parser.add_argument(
        "--out",
        default="dashboard_data.json",
        help="Output JSON path (default: dashboard_data.json)",
    )
    args = parser.parse_args()

    student_id = args.student_id
    topic_id = args.topic_id
    if not student_id or not topic_id:
        def_student, def_topic = get_default_context(args.db)
        student_id = student_id or def_student
        topic_id = topic_id or def_topic
        print(f"[info] Defaulting parameters to student_id='{student_id}', topic_id='{topic_id}'")

    export_dashboard_data(args.db, student_id, topic_id, args.out)