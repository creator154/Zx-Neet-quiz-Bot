import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import psycopg2
from database import setup

# Setup database tables
setup()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

DATABASE_URL = os.environ.get("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cur = conn.cursor()

user_states = {}

# START COMMAND
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Welcome to Advanced Quiz Bot!\n\nUse /create to create new quiz.")

# CREATE QUIZ
@bot.message_handler(commands=['create'])
def create_quiz(message):
    user_states[message.from_user.id] = {"step": "title"}
    bot.send_message(message.chat.id, "Send Quiz Title:")

# HANDLE TEXT
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    # TITLE STEP
    if state["step"] == "title":
        state["title"] = message.text
        state["step"] = "description"
        bot.send_message(message.chat.id, "Send Quiz Description:")
    
    # DESCRIPTION STEP
    elif state["step"] == "description":
        state["description"] = message.text
        state["step"] = "timer"
        bot.send_message(message.chat.id, "Send Timer in seconds (example: 30):")
    
    # TIMER STEP
    elif state["step"] == "timer":
        try:
            timer = int(message.text)
            state["timer"] = timer
            
            # Save quiz
            cur.execute(
                "INSERT INTO quizzes (creator_id, title, description, timer, shuffle) VALUES (%s, %s, %s, %s, %s)",
                (user_id, state["title"], state["description"], state["timer"], "no")
            )
            conn.commit()
            
            bot.send_message(message.chat.id, "Quiz Created Successfully ✅")
            del user_states[user_id]
        
        except:
            bot.send_message(message.chat.id, "Please send valid number.")

# LIST QUIZZES
@bot.message_handler(commands=['myquiz'])
def my_quiz(message):
    user_id = message.from_user.id
    cur.execute("SELECT id, title FROM quizzes WHERE creator_id=%s", (user_id,))
    quizzes = cur.fetchall()
    
    if not quizzes:
        bot.send_message(message.chat.id, "No quizzes found.")
        return
    
    text = "Your Quizzes:\n\n"
    for q in quizzes:
        text += f"ID: {q[0]} | {q[1]}\n"
    
    bot.send_message(message.chat.id, text)

print("Bot Running...")
bot.infinity_polling()
