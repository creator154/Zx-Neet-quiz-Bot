# database.py - SQLite database for Quiz Bot (quizzes, questions, scores)

import sqlite3
import os
from datetime import datetime

DB_FILE = "quizbot.db"

def init_db():
    """Initialize the database if it doesn't exist."""
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE quizzes
                     (quiz_id TEXT PRIMARY KEY, title TEXT, description TEXT, creator_id TEXT, created_at TEXT)''')
        c.execute('''CREATE TABLE questions
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, quiz_id TEXT, question TEXT, options TEXT, correct_option INTEGER, explanation TEXT,
                      FOREIGN KEY(quiz_id) REFERENCES quizzes(quiz_id))''')
        c.execute('''CREATE TABLE scores
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, quiz_id TEXT, user_id TEXT, score INTEGER, total INTEGER, completed_at TEXT,
                      FOREIGN KEY(quiz_id) REFERENCES quizzes(quiz_id))''')
        conn.commit()
        conn.close()
        print("Database initialized.")

def add_quiz(quiz_id, title, description, creator_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    created_at = datetime.now().isoformat()
    c.execute("INSERT INTO quizzes (quiz_id, title, description, creator_id, created_at) VALUES (?, ?, ?, ?, ?)",
              (quiz_id, title, description, creator_id, created_at))
    conn.commit()
    conn.close()

def add_question(quiz_id, question, options, correct_option, explanation):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    options_str = ','.join(options)  # store as comma separated string
    c.execute("INSERT INTO questions (quiz_id, question, options, correct_option, explanation) VALUES (?, ?, ?, ?, ?)",
              (quiz_id, question, options_str, correct_option, explanation))
    conn.commit()
    conn.close()

def get_quiz(quiz_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT title, description FROM quizzes WHERE quiz_id = ?", (quiz_id,))
    result = c.fetchone()
    conn.close()
    return result

def get_questions(quiz_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT question, options, correct_option, explanation FROM questions WHERE quiz_id = ?", (quiz_id,))
    rows = c.fetchall()
    conn.close()
    questions = []
    for row in rows:
        options = row[1].split(',') if row[1] else []
        questions.append({
            'question': row[0],
            'options': options,
            'correct_option_id': row[2],
            'explanation': row[3]
        })
    return questions

def save_score(quiz_id, user_id, score, total):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    completed_at = datetime.now().isoformat()
    c.execute("INSERT INTO scores (quiz_id, user_id, score, total, completed_at) VALUES (?, ?, ?, ?, ?)",
              (quiz_id, user_id, score, total, completed_at))
    conn.commit()
    conn.close()

def get_leaderboard(quiz_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, score, total FROM scores WHERE quiz_id = ? ORDER BY score DESC LIMIT 10", (quiz_id,))
    rows = c.fetchall()
    conn.close()
    return rows
