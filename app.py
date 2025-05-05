import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import logging
import json
import base64
import datetime
import gspread
from google.oauth2.service_account import Credentials

# === ЛОГІ ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Flask App ===
app = Flask(__name__)

# === Telegram Bot App ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
application = Application.builder().token(TELEGRAM_TOKEN).build()

# === Google Sheets авторизація ===
def init_google_sheet():
    encoded = os.getenv("CREDENTIALS_JSON_BASE64")
    credentials_data = base64.b64decode(encoded).decode("utf-8")
    creds = Credentials.from_service_account_info(json.loads(credentials_data))
    gc = gspread.authorize(creds)
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    return gc.open_by_key(spreadsheet_id)

sheet = init_google_sheet()
sheet_apartment = sheet.worksheet("Квартири")
sheet_data = sheet.worksheet("Показники")

# === Обробники команд ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Я працюю.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ваше повідомлення прийнято.")

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# === Webhook маршрут ===
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "ok"

# === Головний запуск ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    application.run_polling()  # Запуск для тестів локально
    # У Render цей блок активний:
    app.run(host="0.0.0.0", port=port)
