import sqlite3

DB_FILE = "quiz.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Quiz table
    c.execute("""
    CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT
    )
    """)
    # Questions table
    c.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER,
        question TEXT,
        options TEXT,
        correct_option INTEGER,
        timer INTEGER,
        shuffle_q INTEGER,
        shuffle_opt INTEGER,
        FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
    )
    """)
    conn.commit()
    conn.close()
