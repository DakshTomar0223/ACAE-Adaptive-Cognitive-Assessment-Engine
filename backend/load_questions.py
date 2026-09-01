import json
import random
import sqlite3
from pathlib import Path

# Input/Output configuration
SEED_FILES = [
    "../seed_questions_physics_kinematics.json",
    "../seed_questions_physics_mechanics.json",
    "../seed_questions_physics_energy.json",
]
MERGED_OUTPUT_FILE = "seed_questions_physics.json"
DB_PATH = "acae.db"
SCHEMA_PATH = "../schema.sql"


def load_and_merge_seed_data(file_paths: list[str]) -> list[dict]:
    """Reads multiple seed JSON files and merges them into a single list."""
    merged_data = []
    for path_str in file_paths:
        file_path = Path(path_str)
        if file_path.is_file():
            with open(file_path, "r", encoding="utf-8") as f:
                questions = json.load(f)
                merged_data.extend(questions)
        else:
            print(f"Warning: File {path_str} not found. Skipping.")
    return merged_data


def shuffle_question_options(questions: list[dict]) -> list[dict]:
    """Shuffles options for each question and updates option labels."""
    processed_questions = []

    for q in questions:
        q_copy = dict(q)
        raw_options = list(q_copy.get("options", []))

        # Shuffle the option list in place
        random.shuffle(raw_options)

        # Re-assign standard A, B, C, D labels post-shuffle
        shuffled_options = []
        for idx, opt in enumerate(raw_options):
            _, text, error_category, is_correct = opt
            label = chr(65 + idx)  # 'A', 'B', 'C', 'D'
            shuffled_options.append([label, text, error_category, is_correct])

        q_copy["options"] = shuffled_options
        processed_questions.append(q_copy)

    return processed_questions


def insert_into_database(
    questions: list[dict], db_path: str, schema_path: str
) -> None:
    """Inserts subjects, topics, questions, and options into SQLite safely."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Execute schema setup if available
    if Path(schema_path).is_file():
        with open(schema_path, "r", encoding="utf-8") as f:
            cursor.executescript(f.read())

    # Ensure default 'physics' subject entry exists
    cursor.execute(
        "INSERT OR IGNORE INTO subjects (subject_id, name) VALUES (?, ?)",
        ("physics", "Physics"),
    )

    # Disable foreign keys temporarily to handle circular reference between questions and options
    cursor.execute("PRAGMA foreign_keys = OFF;")

    for q in questions:
        q_id = q["id"]
        topic_id = q["topic"]
        stem = q["stem"]
        difficulty = q["difficulty"]
        tag_confidence = q.get("tag_confidence", 1.0)
        source = q.get("source", "seed")

        # Auto-populate topics if missing
        topic_name = topic_id.replace("_", " ").title()
        cursor.execute(
            "INSERT OR IGNORE INTO topics (topic_id, subject_id, name) VALUES (?, ?, ?)",
            (topic_id, "physics", topic_name),
        )

        correct_option_id = None
        option_records = []

        for idx, opt in enumerate(q["options"]):
            _, text, error_category, is_correct = opt
            # Generate deterministic option ID bound to position
            option_id = f"{q_id}_opt_{idx + 1}"

            if is_correct:
                correct_option_id = option_id

            option_records.append(
                (option_id, q_id, text, error_category, 1 if is_correct else 0)
            )

        # Upsert Question record
        cursor.execute(
            """
            INSERT INTO questions (
                question_id, topic_id, stem, difficulty, correct_option_id, tag_confidence, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(question_id) DO UPDATE SET
                topic_id=EXCLUDED.topic_id,
                stem=EXCLUDED.stem,
                difficulty=EXCLUDED.difficulty,
                correct_option_id=EXCLUDED.correct_option_id,
                tag_confidence=EXCLUDED.tag_confidence,
                source=EXCLUDED.source
            """,
            (
                q_id,
                topic_id,
                stem,
                difficulty,
                correct_option_id,
                tag_confidence,
                source,
            ),
        )

        # Upsert Option records
        for opt_rec in option_records:
            cursor.execute(
                """
                INSERT INTO options (
                    option_id, question_id, option_text, error_category, is_correct
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(option_id) DO UPDATE SET
                    question_id=EXCLUDED.question_id,
                    option_text=EXCLUDED.option_text,
                    error_category=EXCLUDED.error_category,
                    is_correct=EXCLUDED.is_correct
                """,
                opt_rec,
            )

    cursor.execute("PRAGMA foreign_keys = ON;")
    conn.commit()
    conn.close()


def main():
    # 1. Read & Merge
    raw_questions = load_and_merge_seed_data(SEED_FILES)
    print(f"Loaded {len(raw_questions)} questions total.")

    # 2. Shuffle Options
    shuffled_questions = shuffle_question_options(raw_questions)

    # 3. Save Merged JSON File
    with open(MERGED_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(shuffled_questions, f, indent=2)
    print(f"Saved merged dataset to '{MERGED_OUTPUT_FILE}'.")

    # 4. Insert into SQLite Database
    insert_into_database(shuffled_questions, DB_PATH, SCHEMA_PATH)
    print(f"Successfully loaded questions into '{DB_PATH}'.")


if __name__ == "__main__":
    main()