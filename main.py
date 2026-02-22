import asyncio
from telegram.ext import ApplicationBuilder
from handlers import conv_handler
from database import init_db
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Heroku config var

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set in environment variables")

# Initialize database
init_db()

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Add ConversationHandler
    app.add_handler(conv_handler)
    
    print("Bot running...")

    # Run polling safely
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        print("Asyncio loop error:", e)
