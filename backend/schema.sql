-- ACAE Phase 1 schema
-- Core idea: MCQ options are individually mapped to error categories,
-- so a wrong-option choice is itself diagnostic data, not just "incorrect".

CREATE TABLE IF NOT EXISTS subjects (
    subject_id   TEXT PRIMARY KEY,   -- 'physics' | 'chemistry' | 'math'
    name         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topics (
    topic_id     TEXT PRIMARY KEY,   -- e.g. 'phys_kinematics_2d'
    subject_id   TEXT NOT NULL REFERENCES subjects(subject_id),
    name         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    question_id      TEXT PRIMARY KEY,
    topic_id         TEXT NOT NULL REFERENCES topics(topic_id),
    stem             TEXT NOT NULL,
    difficulty        INTEGER NOT NULL,        -- 1-5
    correct_option_id TEXT NOT NULL,           -- FK to options.option_id
    tag_confidence     REAL DEFAULT 1.0,        -- confidence from tagging pipeline
    source             TEXT DEFAULT 'seed'      -- 'seed' | 'llm_generated' | 'ncert'
);

-- Each option, including the correct one, carries an error-category tag.
-- The correct option's tag is NULL (no error to diagnose).
CREATE TABLE IF NOT EXISTS options (
    option_id       TEXT PRIMARY KEY,
    question_id     TEXT NOT NULL REFERENCES questions(question_id),
    option_text     TEXT NOT NULL,
    error_category  TEXT,   -- NULL if this is the correct option
    is_correct      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS students (
    student_id   TEXT PRIMARY KEY,
    name         TEXT
);

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL REFERENCES students(student_id),
    question_id      TEXT NOT NULL REFERENCES questions(question_id),
    chosen_option_id TEXT NOT NULL REFERENCES options(option_id),
    is_correct       INTEGER NOT NULL,
    time_taken_sec   REAL,
    timestamp        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attempts_student ON attempts(student_id);
CREATE INDEX IF NOT EXISTS idx_options_question ON options(question_id);
