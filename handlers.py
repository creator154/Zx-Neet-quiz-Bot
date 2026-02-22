from database import get_connection, init_db

# Initialize database at bot startup
init_db()

# Example: Save quiz in finish handler
async def shuffle_opt(update, context):
    query = update.callback_query
    await query.answer()
    
    shuffle_q = context.user_data.get("shuffle_q", False)
    shuffle_opt_flag = context.user_data.get("shuffle_opt", False)
    timer_sec = context.user_data.get("timer", 20)
    questions = context.user_data.get("questions", [])

    # Save to DB
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO quizzes (title, timer, shuffle_questions, shuffle_options) VALUES (?, ?, ?, ?)",
        ("My Quiz", timer_sec, int(shuffle_q), int(shuffle_opt_flag))
    )
    quiz_id = cursor.lastrowid

    for poll in questions:
        options = ",".join([opt.text for opt in poll.options])
        correct = poll.correct_option_id
        cursor.execute(
            "INSERT INTO questions (quiz_id, question_text, options, correct_option) VALUES (?, ?, ?, ?)",
            (quiz_id, poll.question, options, correct)
        )

    conn.commit()
    conn.close()

    await query.message.reply_text(
        f"🎉 Quiz Saved Successfully!\nTotal Questions: {len(questions)}"
    )
    context.user_data.clear()
    return -1
