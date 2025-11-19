import sqlite3
import streamlit as st

DB_NAME = "judging.db"

@st.cache_resource
def get_connection():
    # Return a cached SQLite connection
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

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

    conn.commit()


# --- CRUD operations ---

def get_judges():
    conn = get_connection()
    return conn.execute("SELECT * FROM judges ORDER BY id").fetchall()

def insert_judge(name, email):
    conn = get_connection()
    conn.execute("INSERT INTO judges (name, email) VALUES (?, ?)", (name, email))
    conn.commit()

def get_competitors():
    conn = get_connection()
    return conn.execute("SELECT * FROM competitors ORDER BY id").fetchall()

def insert_competitor(name):
    conn = get_connection()
    conn.execute(
        "INSERT INTO competitors (name) VALUES (?)",
        (name,)
    )
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

def get_scores_for_judge(judge_id):
    """
    Return existing scores for a judge as:
      {competitor_id: value}
    """
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
    return conn.execute("""
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
