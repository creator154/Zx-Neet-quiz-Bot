import os
import asyncio
from pyrogram import Client, filters

api_id = int(os.environ.get("API_ID"))
api_hash = os.environ.get("API_HASH")
bot_token = os.environ.get("BOT_TOKEN")

app = Client(
    "neetquizbot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token
)

quiz_data = [
    {
        "question": "2 + 2 = ?",
        "options": ["3", "4", "5", "6"],
        "correct": 1
    },
    {
        "question": "Capital of India?",
        "options": ["Mumbai", "Delhi", "Kolkata", "Chennai"],
        "correct": 1
    }
]

scores = {}
active_polls = {}
max_marks = len(quiz_data) * 4


@app.on_message(filters.command("startquiz") & filters.group)
async def start_quiz(client, message):

    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ["administrator", "creator"]:
        return await message.reply("Only Admin Can Start Quiz ❌")

    scores.clear()
    active_polls.clear()

    await message.reply(
        "🧪 NEET Mock Test Started\n"
        "Marking: +4 Correct | -1 Wrong"
    )

    for q in quiz_data:
        poll = await client.send_poll(
            chat_id=message.chat.id,
            question=q["question"],
            options=q["options"],
            type="quiz",
            correct_option_id=q["correct"],
            open_period=20,
            is_anonymous=False
        )

        active_polls[poll.poll.id] = q["correct"]
        await asyncio.sleep(25)

    await show_result(client, message.chat.id)


@app.on_poll_answer()
async def handle_answer(client, poll_answer):

    poll_id = poll_answer.poll_id
    user_id = poll_answer.user.id

    if poll_id not in active_polls:
        return

    correct_option = active_polls[poll_id]
    selected_option = poll_answer.option_ids[0]

    if user_id not in scores:
        scores[user_id] = 0

    if selected_option == correct_option:
        scores[user_id] += 4
    else:
        scores[user_id] -= 1


async def show_result(client, chat_id):

    result_text = "🏆 NEET Result 🏆\n\n"
    rank = 1

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    for user_id, score in sorted_scores:
        percentage = (score / max_marks) * 100

        result_text += (
            f"{rank}. User ID: {user_id}\n"
            f"   Marks: {score}/{max_marks}\n"
            f"   Percentage: {percentage:.2f}%\n\n"
        )
        rank += 1

    await client.send_message(chat_id, result_text)


app.run()
