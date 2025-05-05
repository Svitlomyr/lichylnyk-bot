import os
import json
import base64
import datetime
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import gspread
from google.oauth2.service_account import Credentials

# === ЛОГУВАННЯ ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === FLASK ===
app = Flask(__name__)
bot_app = None  # Application PTB

# === GOOGLE SHEETS ПІДКЛЮЧЕННЯ ===
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

def get_apartment_info(chat_id):
    values = sheet_apartment.get_all_records()
    for i, row in enumerate(values, start=2):
        if str(row.get("Chat ID")) == str(chat_id):
            return i, row
    return None, None

def add_apartment(chat_id, name, apartment_number=None):
    next_row = len(sheet_apartment.get_all_values()) + 1
    sheet_apartment.update(f"A{next_row}:C{next_row}", [[chat_id, name, apartment_number or ""]])

def save_reading(chat_id, value):
    today = datetime.date.today().isoformat()
    sheet_data.append_row([today, chat_id, value, ""])

def last_reading(chat_id):
    records = sheet_data.get_all_records()
    filtered = [r for r in records if str(r["Chat ID"]) == str(chat_id)]
    if filtered:
        last = filtered[-1]
        return last["Дата"], last["Показник"]
    return None, None

# === ОБРОБНИКИ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name = update.effective_chat.full_name
    row_index, info = get_apartment_info(chat_id)
    if not info:
        add_apartment(chat_id, name)
        await update.message.reply_text("Привіт! Ти зареєстрований. Введи номер своєї квартири у форматі: квартира 37 або кв.37")
    else:
        await update.message.reply_text("Ти вже зареєстрований. Надішли поточний показник лічильника (лише ціле число).")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    name = update.effective_chat.full_name
    row_index, info = get_apartment_info(chat_id)

    if not info:
        add_apartment(chat_id, name)
        await update.message.reply_text("Тебе зареєстровано. Тепер введи номер квартири: квартира 37 або кв.37")
        return

    if not info.get("Квартира"):
        import re
        match = re.search(r"\bкв(?:артир[а-я]*)?\s*(\d{1,4})", text.lower())
        if match:
            apartment_number = match.group(1)
            sheet_apartment.update_cell(row_index, 3, apartment_number)
            await update.message.reply_text(f"Квартира {apartment_number} зареєстрована. Тепер введи поточний показник лічильника.")
        else:
            await update.message.reply_text("Будь ласка, введи номер квартири у форматі: квартира 12 або кв.12")
        return

    if text.isdigit():
        value = int(text)
        today = datetime.date.today()
        if today.day < 21 or today.day > 23:
            await update.message.reply_text("Показники бажано подавати з 21 по 22 числа кожного місяця.")
        last_date, last_value = last_reading(chat_id)
        save_reading(chat_id, value)
        if last_date:
            await update.message.reply_text(f"Показник {value} прийнято. Останній показник: {last_value} (від {last_date})")
        else:
            await update.message.reply_text(f"Показник {value} прийнято. Це перше подання.")
    else:
        await update.message.reply_text("Будь ласка, введи лише ціле число — поточний показник лічильника.")

# === WEBHOOK ===
@app.route(f"/{os.getenv('TELEGRAM_BOT_TOKEN')}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    bot_app.update_queue.put(update)
    return "OK"

@app.route("/", methods=["GET"])
def root():
    return "Bot is running!"

async def init_bot():
    global bot_app
    bot_app = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()

import asyncio
asyncio.run(init_bot())