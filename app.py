import os
from flask import Flask, request
import telegram

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telegram.Bot(token=TOKEN)

app = Flask(__name__)

@app.route("/")
def home():
    return "Бот працює!"

@app.route(f"/{TOKEN}", methods=["POST"])
def receive_update():
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    chat_id = update.message.chat.id
    text = update.message.text.lower()

    if "/start" in text:
        bot.send_message(chat_id=chat_id, text="Привіт! Введи номер своєї квартири.")
    elif "кв" in text:
        bot.send_message(chat_id=chat_id, text=f"Квартира {text} зареєстрована. Введи показник лічильника.")
    elif text.isdigit():
        bot.send_message(chat_id=chat_id, text=f"Показник {text} збережено. Дякую!")
    else:
        bot.send_message(chat_id=chat_id, text="Не зрозумів повідомлення.")

    return "ok"
    if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
