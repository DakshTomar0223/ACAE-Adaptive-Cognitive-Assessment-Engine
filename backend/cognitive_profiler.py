"""
Cognitive Profiler — Phase 2 of ACAE.

Turns a student's raw attempt log (which option they chose per question)
into a confidence-scored profile across the error categories, per topic.
"""
import argparse
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean

MIN_ATTEMPTS_FOR_CONFIDENCE = 8  # per blueprint: single wrong answers are noise

EXCLUDED_FROM_DOMINANCE = frozenset({"careless_attention_slip"})

MIN_TIMED_ATTEMPTS_FOR_TIMING_SIGNAL = 4  # min samples w/ non-null time_taken_sec
TIME_PRESSURE_COLLAPSE_RATIO = 1.4        # wrong-avg / correct-avg within a topic
CALC_SPEED_DEFICIT_RATIO = 1.3            # topic correct-avg / student's overall correct-avg


@dataclass
class TopicProfile:
    topic_id: str
    total_attempts: int = 0
    correct: int = 0
    category_votes: dict = field(default_factory=lambda: defaultdict(int))
    correct_times: list = field(default_factory=list)
    wrong_times: list = field(default_factory=list)

    @property
    def accuracy(self):
        return self.correct / self.total_attempts if self.total_attempts else 0.0

    @property
    def is_confident(self):
        return self.total_attempts >= MIN_ATTEMPTS_FOR_CONFIDENCE

    @property
    def dominant_category(self):
        if not self.category_votes:
            return None, 0.0
        total_wrong = sum(self.category_votes.values())
        if total_wrong == 0:
            return None, 0.0

        eligible = {
            cat: votes
            for cat, votes in self.category_votes.items()
            if cat not in EXCLUDED_FROM_DOMINANCE and votes > 0
        }
        if not eligible:
            return None, 0.0

        cat, votes = sorted(eligible.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        return cat, votes / total_wrong

    def timing_flags(self, student_overall_correct_avg=None):
        flags = []

        if (
            len(self.wrong_times) >= MIN_TIMED_ATTEMPTS_FOR_TIMING_SIGNAL
            and len(self.correct_times) >= 1
        ):
            wrong_avg = mean(self.wrong_times)
            correct_avg = mean(self.correct_times)
            if correct_avg > 0 and wrong_avg / correct_avg >= TIME_PRESSURE_COLLAPSE_RATIO:
                flags.append((
                    "time_pressure_collapse",
                    f"wrong answers avg {wrong_avg:.1f}s vs correct avg "
                    f"{correct_avg:.1f}s ({wrong_avg / correct_avg:.1f}x)",
                ))

        if (
            len(self.correct_times) >= MIN_TIMED_ATTEMPTS_FOR_TIMING_SIGNAL
            and student_overall_correct_avg
            and student_overall_correct_avg > 0
        ):
            topic_correct_avg = mean(self.correct_times)
            ratio = topic_correct_avg / student_overall_correct_avg
            if ratio >= CALC_SPEED_DEFICIT_RATIO:
                flags.append((
                    "calculation_speed_deficit",
                    f"correct answers here avg {topic_correct_avg:.1f}s vs "
                    f"{student_overall_correct_avg:.1f}s overall ({ratio:.1f}x)",
                ))

        return flags


def build_profile(db_path: str, student_id: str) -> dict:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT a.attempt_id, q.topic_id, a.is_correct, o.error_category,
               a.time_taken_sec
        FROM attempts a
        LEFT JOIN questions q ON a.question_id = q.question_id
        LEFT JOIN options o ON a.chosen_option_id = o.option_id
        WHERE a.student_id = ?
        """,
        (student_id,),
    )
    rows = cur.fetchall()
    conn.close()

    profiles: dict[str, TopicProfile] = {}
    for attempt_id, topic_id, is_correct, error_category, time_taken_sec in rows:
        if topic_id is None:
            print(f"[warn] attempt {attempt_id} references a missing question — skipped.")
            continue

        p = profiles.setdefault(topic_id, TopicProfile(topic_id=topic_id))
        p.total_attempts += 1

        if is_correct:
            p.correct += 1
            if time_taken_sec is not None:
                p.correct_times.append(time_taken_sec)
        else:
            if time_taken_sec is not None:
                p.wrong_times.append(time_taken_sec)
            if error_category:
                p.category_votes[error_category] += 1

    return profiles


def other_topics_correct_avg(profiles: dict, topic_id: str):
    times = [
        t
        for other_id, other_p in profiles.items()
        if other_id != topic_id
        for t in other_p.correct_times
    ]
    return mean(times) if times else None


def print_report(profiles: dict):
    if not profiles:
        print("No attempts on record for this student.")
        return

    for topic_id, p in profiles.items():
        overall_correct_avg = other_topics_correct_avg(profiles, topic_id)

        print(f"\n=== Topic: {topic_id} ===")
        print(f"  Attempts: {p.total_attempts}  Accuracy: {p.accuracy:.0%}")
        print(f"  Confidence gate met: {'yes' if p.is_confident else 'no (need more attempts)'}")

        if p.category_votes:
            print("  Error category breakdown:")
            total_wrong = sum(p.category_votes.values())
            for cat, votes in sorted(p.category_votes.items(), key=lambda kv: (-kv[1], kv[0])):
                print(f"    - {cat:<28} {votes}/{total_wrong} wrong answers ({votes / total_wrong:.0%})")

            cat, share = p.dominant_category
            if cat is None:
                print("  >> No clear systematic pattern.")
            elif p.is_confident:
                print(f"  >> DOMINANT WEAK POINT: {cat} ({share:.0%} of wrong answers)")
            else:
                print(f"  >> Provisional signal only (not enough attempts yet): {cat}")
        else:
            print("  No error-category signal (all correct so far, or no tagged wrong answers).")

        for flag_name, detail in p.timing_flags(overall_correct_avg):
            print(f"  >> TIMING FLAG: {flag_name} — {detail}")


def get_default_student_id(db_path: str) -> str:
    """Queries DB for the first active student_id, falling back to 'student_01'."""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT student_id FROM attempts LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
    return "student_01"


def main():
    parser = argparse.ArgumentParser(description="ACAE cognitive profiler")
    parser.add_argument(
        "student_id",
        nargs="?",
        default=None,
        help="Student ID to build a profile for (optional)",
    )
    parser.add_argument(
        "--db", default="acae.db", help="Path to the ACAE SQLite DB (default: acae.db)"
    )
    args = parser.parse_args()

    student_id = args.student_id
    if not student_id:
        student_id = get_default_student_id(args.db)
        print(f"[info] No student_id provided. Defaulting to: '{student_id}'")

    profiles = build_profile(args.db, student_id)
    print_report(profiles)


if __name__ == "__main__":
    main()