import os
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cur = conn.cursor()

def setup():
    cur.execute("""
    CREATE TABLE IF NOT EXISTS quizzes (
        id SERIAL PRIMARY KEY,
        creator_id BIGINT,
        title TEXT,
        description TEXT,
        timer INT,
        shuffle TEXT
    )
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id SERIAL PRIMARY KEY,
        quiz_id INT,
        question TEXT,
        options TEXT[],
        correct_index INT
    )
    """)
    
    conn.commit()
