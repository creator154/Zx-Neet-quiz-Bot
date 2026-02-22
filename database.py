import sqlite3
from sqlite3 import Connection

DB_FILE = "quiz.db"

def get_connection() -> Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Table for quizzes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            timer INTEGER,
            shuffle_questions INTEGER,
            shuffle_options INTEGER
        )
    """)

    # Table for questions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER,
            question_text TEXT,
            options TEXT,
            correct_option INTEGER,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id)
        )
    """)

    conn.commit()
    conn.close()
