import sqlite3
import streamlit as st
import hashlib

DB_NAME = "judging.db"

@st.cache_resource
def get_connection():
    # Return a cached SQLite connection
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _to_dict(row):
    return dict(row) if row else None


def _to_dicts(rows):
    return [dict(r) for r in rows] if rows else []

def init_db():
    # Create tables if they do not exist
    conn = get_connection()
    cur = conn.cursor()

    # Judges table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS judges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        );
    """)

    # Competitors table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS competitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
    """)

    # Scores table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            judge_id INTEGER NOT NULL,
            competitor_id INTEGER NOT NULL,
            value REAL NOT NULL,
            FOREIGN KEY (judge_id) REFERENCES judges(id),
            FOREIGN KEY (competitor_id) REFERENCES competitors(id)
        );
    """)

    # Questions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT NOT NULL
        );
    """)

    # Answers table (per question score)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            judge_id INTEGER NOT NULL,
            competitor_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            value REAL NOT NULL,
            FOREIGN KEY (judge_id) REFERENCES judges(id),
            FOREIGN KEY (competitor_id) REFERENCES competitors(id),
            FOREIGN KEY (question_id) REFERENCES questions(id)
        );
    """)

    # Users table for admin and judge logins
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'judge')),
            judge_id INTEGER,
            FOREIGN KEY (judge_id) REFERENCES judges(id)
        );
    """)

    create_default_admin_if_missing(conn)
    conn.commit()


# --- CRUD operations ---

def get_judges():
    # List judges in creation order
    conn = get_connection()
    rows = conn.execute("SELECT * FROM judges ORDER BY id").fetchall()
    return _to_dicts(rows)

def get_judges_with_user():
    # Judges joined with their login username
    conn = get_connection()
    rows = conn.execute("""
        SELECT j.*, u.username
        FROM judges j
        LEFT JOIN users u ON u.judge_id = j.id AND u.role = 'judge'
        ORDER BY j.id
    """).fetchall()
    return _to_dicts(rows)

def insert_judge(name, email):
    # Insert judge without creating a user
    conn = get_connection()
    conn.execute("INSERT INTO judges (name, email) VALUES (?, ?)", (name, email))
    conn.commit()

def create_judge_account(name, email, username, password):
    """
    Create judge record and associated user account.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO judges (name, email) VALUES (?, ?)", (name, email))
        judge_id = cur.lastrowid
        cur.execute(
            "INSERT INTO users (username, password_hash, role, judge_id) VALUES (?, ?, 'judge', ?)",
            (username, hash_password(password), judge_id)
        )
    except sqlite3.IntegrityError:
        conn.rollback()
        raise
    conn.commit()
    return judge_id

def get_judge_by_id(judge_id):
    # Fetch single judge row
    conn = get_connection()
    row = conn.execute("SELECT * FROM judges WHERE id = ?", (judge_id,)).fetchone()
    return _to_dict(row)

def update_judge_account(judge_id, name, email, username, password=None):
    # Update judge profile and linked login; password optional
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE judges SET name = ?, email = ? WHERE id = ?",
            (name, email, judge_id)
        )
        if password:
            cur.execute(
                "UPDATE users SET username = ?, password_hash = ? WHERE judge_id = ?",
                (username, hash_password(password), judge_id)
            )
        else:
            cur.execute(
                "UPDATE users SET username = ? WHERE judge_id = ?",
                (username, judge_id)
            )
    except sqlite3.IntegrityError:
        conn.rollback()
        raise
    conn.commit()

def delete_judge_account(judge_id):
    # Remove judge, their login, and their scores
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM scores WHERE judge_id = ?", (judge_id,))
    cur.execute("DELETE FROM answers WHERE judge_id = ?", (judge_id,))
    cur.execute("DELETE FROM users WHERE judge_id = ?", (judge_id,))
    cur.execute("DELETE FROM judges WHERE id = ?", (judge_id,))
    conn.commit()

def get_competitors():
    # List competitors in creation order
    conn = get_connection()
    rows = conn.execute("SELECT * FROM competitors ORDER BY id").fetchall()
    return _to_dicts(rows)

def insert_competitor(name):
    # Add a competitor
    conn = get_connection()
    conn.execute(
        "INSERT INTO competitors (name) VALUES (?)",
        (name,)
    )
    conn.commit()

def update_competitor(competitor_id, name):
    # Rename a competitor
    conn = get_connection()
    conn.execute(
        "UPDATE competitors SET name = ? WHERE id = ?",
        (name, competitor_id)
    )
    conn.commit()

def delete_competitor(competitor_id):
    # Remove competitor and their scores
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM scores WHERE competitor_id = ?", (competitor_id,))
    cur.execute("DELETE FROM answers WHERE competitor_id = ?", (competitor_id,))
    cur.execute("DELETE FROM competitors WHERE id = ?", (competitor_id,))
    conn.commit()


def replace_scores_for_judge(judge_id, scores_dict):
    # Replace all scores for a judge
    conn = get_connection()

    conn.execute("DELETE FROM scores WHERE judge_id = ?", (judge_id,))
    for competitor_id, value in scores_dict.items():
        conn.execute(
            "INSERT INTO scores (judge_id, competitor_id, value) VALUES (?, ?, ?)",
            (judge_id, competitor_id, value)
        )
    conn.commit()

def save_answers_for_judge(judge_id, competitor_id, answers_dict):
    # Save per-question answers and aggregate into scores table
    conn = get_connection()
    cur = conn.cursor()

    # Clear previous answers/scores for this judge+competitor
    cur.execute(
        "DELETE FROM answers WHERE judge_id = ? AND competitor_id = ?",
        (judge_id, competitor_id)
    )
    cur.execute(
        "DELETE FROM scores WHERE judge_id = ? AND competitor_id = ?",
        (judge_id, competitor_id)
    )

    # Insert answers
    for question_id, value in answers_dict.items():
        cur.execute(
            "INSERT INTO answers (judge_id, competitor_id, question_id, value) VALUES (?, ?, ?, ?)",
            (judge_id, competitor_id, question_id, value)
        )

    # Aggregate average and store in scores table
    if answers_dict:
        avg_value = sum(answers_dict.values()) / len(answers_dict)
        cur.execute(
            "INSERT INTO scores (judge_id, competitor_id, value) VALUES (?, ?, ?)",
            (judge_id, competitor_id, avg_value)
        )
    conn.commit()

def get_scores_for_judge(judge_id):
    # Return existing scores for a judge as {competitor_id: value}
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT competitor_id, value FROM scores WHERE judge_id = ?",
        (judge_id,)
    )
    rows = cur.fetchall()
    return {row["competitor_id"]: row["value"] for row in rows}

def get_leaderboard():
    # Return totals and averages per competitor
    conn = get_connection()
    rows = conn.execute("""
        SELECT 
            c.id AS competitor_id,
            c.name AS competitor_name,
            COUNT(s.id) AS num_scores,
            COALESCE(SUM(s.value), 0) AS total_score,
            COALESCE(AVG(s.value), 0) AS avg_score
        FROM competitors c
        LEFT JOIN scores s ON c.id = s.competitor_id
        GROUP BY c.id, c.name
        ORDER BY avg_score DESC;
    """).fetchall()
    return _to_dicts(rows)


# --- Questions/answers ---

def get_questions():
    # List all questions
    conn = get_connection()
    rows = conn.execute("SELECT * FROM questions ORDER BY id").fetchall()
    return _to_dicts(rows)

def insert_question(prompt):
    # Add a question
    conn = get_connection()
    conn.execute("INSERT INTO questions (prompt) VALUES (?)", (prompt,))
    conn.commit()

def update_question(question_id, prompt):
    # Update question text
    conn = get_connection()
    conn.execute("UPDATE questions SET prompt = ? WHERE id = ?", (prompt, question_id))
    conn.commit()

def delete_question(question_id):
    # Delete question and its answers
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM answers WHERE question_id = ?", (question_id,))
    cur.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    conn.commit()

def get_answers_for_judge_competitor(judge_id, competitor_id):
    # Return answers for a judge+competitor as {question_id: value}
    conn = get_connection()
    rows = conn.execute(
        "SELECT question_id, value FROM answers WHERE judge_id = ? AND competitor_id = ?",
        (judge_id, competitor_id)
    ).fetchall()
    return {row["question_id"]: row["value"] for row in rows}


# --- Auth helpers ---

def hash_password(password: str) -> str:
    # Simple SHA256 password hash
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def create_default_admin_if_missing(conn):
    # Seed a default admin if none exists
    cur = conn.execute("SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin'")
    row = cur.fetchone()
    if row and row["cnt"] == 0:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, judge_id) VALUES (?, ?, 'admin', NULL)",
            ("admin", hash_password("admin"))
        )

def authenticate_user(username, password):
    # Validate credentials and return user row
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    if row and row["password_hash"] == hash_password(password):
        return _to_dict(row)
    return None
