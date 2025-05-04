
import logging
import os
import json
import base64
import gspread
from google.oauth2 import service_account
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Розкодування credentials.json
credentials_json = base64.b64decode(os.environ["CREDENTIALS_JSON_BASE64"]).decode("utf-8")
info = json.loads(credentials_json)

# Додано правильні scopes
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = service_account.Credentials.from_service_account_info(info, scopes=scope)

# Авторизація в Google Sheets
gc = gspread.authorize(creds)
spreadsheet = gc.open_by_key(os.environ["SPREADSHEET_ID"])

# Телеграм токен
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_IDS = os.environ.get("ADMIN_CHAT_IDS", "").split(",")

# Проста команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Я бот для збору показників електролічильника.")

# Запуск бота
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()

if __name__ == "__main__":
    main()
