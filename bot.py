import os
import random
import requests
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io

# Environment variables
BOT_TOKENS = os.getenv("BOT_TOKENS").split(",")  # List of bot tokens (comma-separated)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
IMDB_API_KEY = os.getenv("IMDB_API_KEY", "f054c7d2")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyD4-CYpnPbNDH09iUOwcN8mturxVwc4HMM")

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Function to generate AI content
def generate_ai_content(prompt: str) -> str:
    try:
        response = model.generate_content(prompt)
        return response.text if response else "No response generated."
    except Exception as e:
        print(f"Error generating AI response: {e}")
        return "Error generating AI response."

# Function to delete bot's messages after a delay
async def delete_bot_message(context):
    data = context.job.data
    message = data.get("message")
    if message:
        try:
            await message.delete()
        except Exception as e:
            print(f"Error deleting message: {e}")

# Greeting based on time of day
def get_time_based_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good Morning!"
    elif 12 <= hour < 18:
        return "Good Afternoon!"
    elif 18 <= hour < 22:
        return "Good Evening!"
    else:
        return "Good Night!"

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    greeting = get_time_based_greeting()
    welcome_text = f"{greeting}😊\n\nWelcome to the bot!"
    message = await update.message.reply_text(welcome_text)
    context.job_queue.run_once(delete_bot_message, 100, data={"message": message})

async def fetch_movie_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    movie_name = update.message.text.strip()
    url = f"http://www.omdbapi.com/?t={movie_name}&apikey={IMDB_API_KEY}"
    response = requests.get(url)
    data = response.json()

    if data.get("Response") == "True":
        reply_text = (
            f"🎬 *Title*: {data.get('Title')}\n"
            f"📅 *Year*: {data.get('Year')}\n"
            f"⭐ *IMDb Rating*: {data.get('imdbRating')}\n"
            f"🎭 *Genre*: {data.get('Genre')}\n"
            f"🕒 *Runtime*: {data.get('Runtime')}\n"
            f"🎥 *Director*: {data.get('Director')}\n"
            f"📝 *Plot*: {data.get('Plot')}\n"
            f"🎞️ *Cast*: {data.get('Actors')}\n"
        )
        poster_url = data.get("Poster")
        download_button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Download Now (PREMIUM Only)💛", url="https://telegra.ph/SORRY-You-are-not-premium-user-01-07")]]
        )
        if poster_url != "N/A":
            message = await context.bot.send_photo(
                chat_id=update.message.chat_id,
                photo=poster_url,
                caption=reply_text,
                parse_mode="Markdown",
                reply_markup=download_button
            )
        else:
            message = await update.message.reply_text(
                reply_text,
                parse_mode="Markdown",
                reply_markup=download_button
            )
    else:
        ai_response = generate_ai_content(f"Can you describe the movie '{movie_name}'?")
        message = await update.message.reply_text(
            f"Movie not found in IMDb. Here's an AI-generated description👇:\n\n{ai_response}😊"
        )
    context.job_queue.run_once(delete_bot_message, 100, data={"message": message})

async def ai_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        message = await update.message.reply_text("Please provide a question. Usage: /ai <your question>😊")
        context.job_queue.run_once(delete_bot_message, 100, data={"message": message})
        return
    question = " ".join(context.args)
    ai_reply = generate_ai_content(question)
    message = await update.message.reply_text(ai_reply)
    context.job_queue.run_once(delete_bot_message, 100, data={"message": message})

# Main function to initialize multiple bots
def main():
    applications = []
    for i, token in enumerate(BOT_TOKENS):
        app = Application.builder().token(token).build()

        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("ai", ai_response))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), fetch_movie_info))

        # Run webhook for this bot
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", 10000)) + i,  # Unique port for each bot
            url_path=token,
            webhook_url=f"{WEBHOOK_URL}/{token}",
        )
        applications.append(app)

if __name__ == "__main__":
    main()
