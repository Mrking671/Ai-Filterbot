import os
import requests
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from datetime import datetime

# Environment variables
BOT_TOKENS = os.getenv("BOT_TOKENS").split(",")  # List of bot tokens (comma-separated)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
IMDB_API_KEY = os.getenv("IMDB_API_KEY", "f054c7d2")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyB4pvkedwMTVVjPp-OzbmTL8M")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Add your channel's ID here

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

# Function to search files in the channel
async def search_files_in_channel(channel_id: str, movie_name: str, context: ContextTypes.DEFAULT_TYPE):
    try:
        files = []
        async for message in context.bot.get_chat_history(channel_id):
            if movie_name.lower() in (message.caption or "").lower() or movie_name.lower() in (message.document.file_name or "").lower():
                if message.document or message.video:
                    files.append(message)
        return files
    except Exception as e:
        print(f"Error searching for files: {e}")
        return []

# Function to fetch movie info and related files
async def fetch_movie_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    movie_name = update.message.text.strip()

    # Fetch movie details from IMDb
    url = f"http://www.omdbapi.com/?t={movie_name}&apikey={IMDB_API_KEY}"
    response = requests.get(url)
    data = response.json()

    if data.get("Response") == "True":
        # Prepare movie details text
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

        # Search for related files in the channel
        files = await search_files_in_channel(CHANNEL_ID, movie_name, context)

        # Create download buttons for related files
        buttons = []
        if files:
            for file in files:
                file_name = file.document.file_name if file.document else "Video File"
                buttons.append([InlineKeyboardButton(file_name, callback_data=f"download_{file.message_id}")])
        else:
            reply_text += "\n\n*No files found related to this movie in the channel.*"

        # Add buttons for IMDb poster and downloads
        if poster_url != "N/A":
            message = await context.bot.send_photo(
                chat_id=update.message.chat_id,
                photo=poster_url,
                caption=reply_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
            )
        else:
            message = await update.message.reply_text(
                reply_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
            )
    else:
        ai_response = generate_ai_content(f"Can you describe the movie '{movie_name}'?")
        message = await update.message.reply_text(
            f"Movie not found in IMDb. Here's an AI-generated description👇:\n\n{ai_response}😊"
        )
    context.job_queue.run_once(delete_bot_message, 100, data={"message": message})

# Function to handle download button clicks
async def download_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("download_"):
        return
    message_id = int(query.data.split("_")[1])

    try:
        # Forward the file to the user
        file_message = await context.bot.forward_message(
            chat_id=query.message.chat_id,
            from_chat_id=CHANNEL_ID,
            message_id=message_id
        )
        context.job_queue.run_once(delete_bot_message, 100, data={"message": file_message})
    except Exception as e:
        print(f"Error forwarding file: {e}")
        await query.message.reply_text("Unable to fetch the file. Please try again later.")

# AI response handler
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
        app.add_handler(CallbackQueryHandler(download_file))

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
