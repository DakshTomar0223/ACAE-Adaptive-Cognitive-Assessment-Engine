"""
Remedial Engine — Phase 4 of ACAE.

Maps error categories from topic_taxonomy.json to structured remedial plans,
including a summary note, a 3-5 step drill sequence, and diagnostic question IDs
from the question bank.
"""

REMEDIAL_CATALOG = {
    "conceptual_misunderstanding": {
        "summary_note": (
            "This isn't a slip — the underlying model needs revisiting. Go back "
            "to first principles for this concept before more practice questions."
        ),
        "drill_sequence": [
            "1. State the fundamental law or definition in your own words without mathematical symbols.",
            "2. Identify the core assumption or boundary condition that contradicts your previous mental model.",
            "3. Solve 2 low-difficulty conceptual verification questions focused on 'Why' rather than calculation.",
            "4. Write down the explicit distinction between your misconception and the correct physical principle."
        ],
        "diagnostic_examples": ["phys_kin_01", "phys_mech_01"]
    },
    "procedural_error": {
        "summary_note": (
            "Your setup is right — the breakdown is in execution. Slow down at "
            "the algebra/calculus step and re-derive rather than pattern-matching."
        ),
        "drill_sequence": [
            "1. Write out every single algebraic transition explicitly without skipping intermediary lines.",
            "2. Perform dimensional analysis on the symbolic solution before substituting numerical values.",
            "3. Re-evaluate boundary conditions (e.g., t=0, x=0) to verify intermediate integration or simplification steps.",
            "4. Work through 3 step-by-step procedural re-derivation exercises."
        ],
        "diagnostic_examples": ["phys_kin_04", "phys_mech_02"]
    },
    "visualization_spatial": {
        "summary_note": (
            "The trap is in the picture, not the math. Before solving, redraw the "
            "diagram and label every vector's direction explicitly — don't reuse a "
            "mental image from a similar-looking problem."
        ),
        "drill_sequence": [
            "1. Sketch a fresh, clean diagram double the standard size on blank paper.",
            "2. Establish a clear Cartesian coordinate frame (+x, +y, +z) and mark vector components explicitly.",
            "3. Verify trigonometric projections (sin vs. cos) against physical boundary angles (0° and 90°).",
            "4. Complete 2 geometric translation and component-decomposition drills."
        ],
        "diagnostic_examples": ["phys_kin_02", "phys_kin_15"]
    },
    "logical_fallacy": {
        "summary_note": (
            "Reasoning chain contains an invalid inference step. Isolate the logical leap and test symmetry or extremes before concluding."
        ),
        "drill_sequence": [
            "1. Write out the logical deduction chain in an 'If A then B because C' structure.",
            "2. Test extreme boundary cases (e.g., mass=0, angle=0°, infinity) to verify if the inference holds.",
            "3. Search for hidden, unstated assumptions in your deduction chain.",
            "4. Practice 3 counter-example identification exercises."
        ],
        "diagnostic_examples": ["phys_kin_03", "phys_mech_13"]
    },
    "calculation_speed_deficit": {
        "summary_note": (
            "Method is correct but too slow under time pressure. Drill the "
            "arithmetic/algebra sub-steps in isolation to build speed."
        ),
        "drill_sequence": [
            "1. Isolate the target numerical or algebraic manipulation sub-routine.",
            "2. Run timed sprint drills (60 seconds per step) focusing purely on arithmetic simplification.",
            "3. Memorize common fractional/trigonometric values and standard square roots.",
            "4. Perform 3 rapid-fire execution drills with a countdown timer."
        ],
        "diagnostic_examples": ["phys_kin_04", "phys_mech_08"]
    },
    "conceptual_synthesis_failure": {
        "summary_note": (
            "Each sub-concept is fine in isolation; the gap is combining them. "
            "Try explicitly listing which concepts a mixed problem draws on before solving."
        ),
        "drill_sequence": [
            "1. Break the problem down into distinct sub-domains (e.g., Kinematics + Energy Conservation).",
            "2. Write out the bridge equation that links the primary variable of Domain A to Domain B.",
            "3. Solve each component independently before substituting into the bridge equation.",
            "4. Complete 2 multi-topic integration drills."
        ],
        "diagnostic_examples": ["phys_kin_12", "phys_eng_13"]
    },
    "careless_attention_slip": {
        "summary_note": (
            "No systematic pattern detected — likely isolated slips. Keep an eye "
            "on it, but this doesn't need a dedicated remedial track yet."
        ),
        "drill_sequence": [
            "1. Highlight key units, signs (+/-), and exact prompt directives (e.g., 'magnitude' vs. 'vector').",
            "2. Double-check number transcription between lines of scratchpad work.",
            "3. Verify that final answer units match the requested physical dimension."
        ],
        "diagnostic_examples": ["phys_kin_05", "phys_mech_11"]
    },
    "formula_misapplication": {
        "summary_note": (
            "You're pulling the right formula but not checking whether its "
            "conditions actually hold here. Before applying it, write out the "
            "assumptions the formula requires."
        ),
        "drill_sequence": [
            "1. List the strict prerequisite conditions required by the formula (e.g., constant acceleration).",
            "2. Cross-check each condition against the explicit constraints given in the problem statement.",
            "3. Derive the formula from first principles if conditions are variable rather than constant.",
            "4. Perform 3 formula-validity checklist drills."
        ],
        "diagnostic_examples": ["phys_kin_01", "phys_mech_01"]
    },
    "time_pressure_collapse": {
        "summary_note": (
            "Accuracy drops specifically under timed conditions. Practice this "
            "topic exclusively in timed mock sets, not untimed drills."
        ),
        "drill_sequence": [
            "1. Set a strict countdown timer matching target exam pacing (e.g., 2 minutes per question).",
            "2. Practice strict 30-second triage: immediately pass on high-complexity setups during round 1.",
            "3. Conduct timed micro-bursts of 5 questions under simulated pressure.",
            "4. Review performance degradation factors between timed vs. untimed runs."
        ],
        "diagnostic_examples": ["phys_kin_12", "phys_eng_03"]
    }
}


def get_remedial_plan(category: str) -> dict:
    """Returns the complete remedial payload (summary note, drill sequence, diagnostic examples)
    for a given error category.
    """
    fallback = {
        "summary_note": "No remedial template written yet.",
        "drill_sequence": ["1. Review general topic fundamentals."],
        "diagnostic_examples": []
    }
    return REMEDIAL_CATALOG.get(category, fallback)


def get_remedial_note(category: str) -> str:
    """Returns the summary remedial note string for backward compatibility."""
    return get_remedial_plan(category)["summary_note"]