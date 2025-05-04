import logging
import os
import json
import base64
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.background import BackgroundScheduler
import gspread
from google.oauth2.service_account import Credentials

# === ЛОГУВАННЯ ===
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

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

# === ДОПОМОЖНІ ФУНКЦІЇ ===
def get_apartment_info(chat_id):
    try:
        values = sheet_apartment.get_all_records()
        for i, row in enumerate(values, start=2):  # рядок 2 – бо перший — заголовки
            if str(row.get("Chat ID")) == str(chat_id):
                return i, row
        return None, None
    except Exception as e:
        logger.error(f"Error fetching apartment info: {e}")
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

def get_users_missing_data(date_str):
    apartment_data = sheet_apartment.get_all_records()
    submitted_ids = [str(row["Chat ID"]) for row in sheet_data.get_all_records() if row["Дата"] == date_str]
    return [row for row in apartment_data if str(row.get("Chat ID")) not in submitted_ids]

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

    # Реєстрація квартири
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

    # Надсилання показника
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

# === НАГАДУВАННЯ ===
async def send_reminders(app: Application):
    today = datetime.date.today()
    day = today.day
    if day == 21:
        message = "Нагадування: подайте показник лічильника електроенергії до 22 числа."
    elif day == 22:
        message = "Останній день подати показники електроенергії. Надішліть поточний показник."
    elif day == 23:
        users = get_users_missing_data(today.isoformat())
        message = "УВАГА! Ви ще не подали показник лічильника. Надішліть його зараз."
        for user in users:
            try:
                await app.bot.send_message(chat_id=user["Chat ID"], text=message)
            except Exception as e:
                logger.error(f"Не вдалося надіслати повідомлення: {e}")
        admins = os.getenv("ADMIN_CHAT_IDS", "").split(",")
        if admins:
            text = f"Квартири, які не подали показник: {[u['Квартира'] for u in users]}"
            for admin in admins:
                try:
                    await app.bot.send_message(chat_id=int(admin), text=text)
                except:
                    pass
        return
    else:
        return

    values = sheet_apartment.get_all_records()
    for row in values:
        chat_id = row.get("Chat ID")
        if chat_id:
            try:
                await app.bot.send_message(chat_id=chat_id, text=message)
            except Exception as e:
                logger.warning(f"Не вдалося надіслати нагадування: {e}")

# === ЗАПУСК ===
async def main():
    app = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: app.create_task(send_reminders(app)), "cron", hour=10, minute=0)
    scheduler.start()

    logger.info("Бот запущено")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())