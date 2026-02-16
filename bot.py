import os
from pyrogram import Client, filters
from pymongo import MongoClient
from questions import quiz_data

# ================= ENV =================
api_id = int(os.environ.get("API_ID"))
api_hash = os.environ.get("API_HASH")
bot_token = os.environ.get("BOT_TOKEN")
mongo_url = os.environ.get("MONGO_URL")

# ================= APP =================
app = Client(
    "neetquizbot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token
)

# ================= DATABASE =================
mongo = MongoClient(mongo_url)
db = mongo["neet_quiz"]
users = db["users"]

# ================= START COMMAND =================
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "🎯 Welcome to NEET Quiz Bot!\n\nType /quiz to start quiz."
    )

# ================= QUIZ COMMAND =================
@app.on_message(filters.command("quiz"))
async def send_quiz(client, message):
    for q in quiz_data:
        await client.send_poll(
            chat_id=message.chat.id,
            question=q["question"],
            options=q["options"],
            type="quiz",
            correct_option_id=q["answer"],
            is_anonymous=False
        )

# ================= POLL ANSWER HANDLER =================
@app.on_message(filters.poll_answer)
async def handle_poll_answer(client, message):

    poll = message.poll_answer
    user_id = poll.user.id
    selected_option = poll.option_ids[0]

    # find correct answer
    correct_option = None
    for q in quiz_data:
        if q["answer"] == selected_option:
            correct_option = q["answer"]
            break

    # get user data
    user = users.find_one({"user_id": user_id})

    if not user:
        users.insert_one({
            "user_id": user_id,
            "score": 0,
            "attempted": 0
        })
        user = users.find_one({"user_id": user_id})

    score = user["score"]
    attempted = user["attempted"]

    # NEET Marking
    if selected_option == correct_option:
        score += 4
    else:
        score -= 1

    attempted += 1

    users.update_one(
        {"user_id": user_id},
        {"$set": {"score": score, "attempted": attempted}}
    )

# ================= RESULT COMMAND =================
@app.on_message(filters.command("result"))
async def result(client, message):

    user = users.find_one({"user_id": message.from_user.id})

    if not user:
        return await message.reply_text("No quiz attempted yet.")

    score = user["score"]
    attempted = user["attempted"]

    total_marks = attempted * 4
    percentage = 0

    if total_marks > 0:
        percentage = (score / total_marks) * 100

    await message.reply_text(
        f"📊 NEET Quiz Result\n\n"
        f"Questions Attempted: {attempted}\n"
        f"Score: {score}\n"
        f"Percentage: {percentage:.2f}%"
    )

# ================= RUN =================
app.run()
