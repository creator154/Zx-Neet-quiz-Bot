import os
import asyncio
from pyrogram import Client, filters
from pymongo import MongoClient
from questions import quiz_data

# Environment Variables (Heroku Config Vars)
api_id = int(os.environ.get("API_ID"))
api_hash = os.environ.get("API_HASH")
bot_token = os.environ.get("BOT_TOKEN"))
mongo_url = os.environ.get("MONGO_URL")

app = Client(
    "neetquizbot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token
)

mongo = MongoClient(mongo_url)
db = mongo.neetquiz
scores = db.scores

active_polls = {}
total_questions = len(quiz_data)
max_marks = total_questions * 4


@app.on_message(filters.command("startquiz") & filters.group)
async def start_quiz(client, message):

    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ["administrator", "creator"]:
        return await message.reply("Only Admin Can Start Quiz ❌")

    scores.delete_many({})
    active_polls.clear()

    await message.reply(
        "🧪 NEET Mock Test Started\n\n"
        "Marking Scheme:\n"
        "✅ +4 Correct\n"
        "❌ -1 Wrong\n"
        "⏳ 0 Unattempted"
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

    if selected_option == correct_option:
        marks = 4
    else:
        marks = -1

    scores.update_one(
        {"user_id": user_id},
        {"$inc": {"score": marks}},
        upsert=True
    )


async def show_result(client, chat_id):

    result_text = "🏆 NEET Mock Test Result 🏆\n\n"
    rank = 1

    for user in scores.find().sort("score", -1):
        score = user.get("score", 0)
        percentage = (score / max_marks) * 100

        result_text += (
            f"{rank}. User ID: {user['user_id']}\n"
            f"   Marks: {score}/{max_marks}\n"
            f"   Percentage: {percentage:.2f}%\n\n"
        )
        rank += 1

    await client.send_message(chat_id, result_text)


@app.on_message(filters.command("stopquiz") & filters.group)
async def stop_quiz(client, message):
    active_polls.clear()
    await message.reply("Quiz Stopped ❌")


app.run()
