"""
Seeds a small distractor-mapped question bank for Physics (kinematics/
mechanics, chosen per the blueprint as the cleanest visualization-vs-
calculation split) and simulates one student's attempt log with a
DELIBERATE dominant weak point, so the profiler has something real to find.

Run: python seed_and_simulate.py
Produces: acae_demo.db
"""
import sqlite3
import random
import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "acae_demo.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

random.seed(7)

# --- Seed question bank -----------------------------------------------
# Each question has 4 options: 1 correct + 3 wrong, each wrong option
# mapped to a specific error category. This is the diagnostic instrument
# described in the blueprint.

QUESTIONS = [
    {
        "id": "phys_q1", "topic": "phys_kinematics_2d",
        "stem": "A ball is thrown at 30 deg above horizontal at 20 m/s. Find max height.",
        "difficulty": 2,
        "options": [
            ("A", "5.1 m", None, True),
            ("B", "10.2 m", "formula_misapplication", False),   # used full v, not v*sin(theta)
            ("C", "20.4 m", "visualization_spatial", False),    # confused height axis with range axis
            ("D", "2.5 m", "procedural_error", False),          # arithmetic slip in g/2 term
        ],
    },
    {
        "id": "phys_q2", "topic": "phys_kinematics_2d",
        "stem": "Two vectors A (3,4) and B (4,-3) are added. Find resultant magnitude.",
        "difficulty": 2,
        "options": [
            ("A", "5.0", "visualization_spatial", False),  # added magnitudes directly, ignored direction
            ("B", "7.07", None, True),
            ("C", "1.0", "procedural_error", False),       # subtracted instead of added components
            ("D", "24.0", "conceptual_misunderstanding", False),  # multiplied components (dot-product confusion)
        ],
    },
    {
        "id": "phys_q3", "topic": "phys_kinematics_2d",
        "stem": "A projectile's velocity vector at the top of its trajectory points in which direction?",
        "difficulty": 1,
        "options": [
            ("A", "Horizontal, in direction of motion", None, True),
            ("B", "Straight down", "visualization_spatial", False),
            ("C", "Zero vector", "conceptual_misunderstanding", False),
            ("D", "Along the original launch angle", "visualization_spatial", False),
        ],
    },
    {
        "id": "phys_q4", "topic": "phys_kinematics_2d",
        "stem": "A block on an incline (angle theta) — which free-body diagram correctly shows normal force direction?",
        "difficulty": 3,
        "options": [
            ("A", "Perpendicular to incline surface", None, True),
            ("B", "Vertically upward", "visualization_spatial", False),
            ("C", "Along the incline surface", "visualization_spatial", False),
            ("D", "At angle theta from vertical, pointing into surface", "visualization_spatial", False),
        ],
    },
    {
        "id": "phys_q5", "topic": "phys_kinematics_2d",
        "stem": "Given x(t) = 3t^2 - 2t, find velocity at t=2s.",
        "difficulty": 2,
        "options": [
            ("A", "10 m/s", None, True),
            ("B", "8 m/s", "procedural_error", False),   # differentiation slip
            ("C", "16 m/s", "formula_misapplication", False),  # used avg velocity formula instead
            ("D", "5 m/s", "careless_attention_slip", False),
        ],
    },
    {
        "id": "phys_q6", "topic": "phys_kinematics_2d",
        "stem": "A ball is dropped from a rotating platform's edge — sketch its path as seen from ABOVE (ground frame).",
        "difficulty": 3,
        "options": [
            ("A", "Straight line, tangent to the circle at release", None, True),
            ("B", "Continues in a circular arc", "visualization_spatial", False),
            ("C", "Spirals inward", "visualization_spatial", False),
            ("D", "Straight line radially outward", "visualization_spatial", False),
        ],
    },
]

STUDENT_ID = "demo_student_01"


def build_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())

    conn.execute("INSERT INTO subjects VALUES ('physics', 'Physics')")
    conn.execute(
        "INSERT INTO topics VALUES ('phys_kinematics_2d', 'physics', '2D Kinematics & Mechanics')"
    )
    conn.execute("INSERT INTO students VALUES (?, 'Demo Student')", (STUDENT_ID,))

    for q in QUESTIONS:
        correct_opt_id = None
        for letter, text, err_cat, is_correct in q["options"]:
            opt_id = f"{q['id']}_{letter}"
            if is_correct:
                correct_opt_id = opt_id
        conn.execute(
            "INSERT INTO questions VALUES (?, ?, ?, ?, ?, ?, ?)",
            (q["id"], q["topic"], q["stem"], q["difficulty"], correct_opt_id, 1.0, "seed"),
        )
        for letter, text, err_cat, is_correct in q["options"]:
            opt_id = f"{q['id']}_{letter}"
            conn.execute(
                "INSERT INTO options VALUES (?, ?, ?, ?, ?)",
                (opt_id, q["id"], text, err_cat, int(is_correct)),
            )
    conn.commit()
    return conn


def simulate_attempts(conn, bias_category="visualization_spatial", n_rounds=4):
    """
    Simulates the demo student attempting the question bank n_rounds times.
    On questions with a wrong-option mapped to `bias_category`, the student
    picks it 70% of the time (simulating a real, recurring weak point) —
    otherwise picks correctly or a random other wrong option.
    """
    cur = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc)

    for round_i in range(n_rounds):
        for q in QUESTIONS:
            options = q["options"]
            biased_wrong = [o for o in options if o[2] == bias_category]
            correct = [o for o in options if o[3]][0]
            other_wrong = [o for o in options if not o[3] and o[2] != bias_category]

            roll = random.random()
            if biased_wrong and roll < 0.70:
                chosen = biased_wrong[0]
            elif roll < 0.85:
                chosen = correct
            elif other_wrong:
                chosen = random.choice(other_wrong)
            else:
                chosen = correct

            opt_id = f"{q['id']}_{chosen[0]}"
            ts = (now - datetime.timedelta(days=(n_rounds - round_i))).isoformat()
            cur.execute(
                "INSERT INTO attempts (student_id, question_id, chosen_option_id, is_correct, time_taken_sec, timestamp)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    STUDENT_ID,
                    q["id"],
                    opt_id,
                    int(chosen[3]),
                    round(random.uniform(20, 90), 1),
                    ts,
                ),
            )
    conn.commit()


if __name__ == "__main__":
    conn = build_db()
    simulate_attempts(conn)
    print(f"Seeded {len(QUESTIONS)} questions and simulated attempts for '{STUDENT_ID}'.")
    print(f"DB written to {DB_PATH}")