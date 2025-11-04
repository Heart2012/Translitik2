from flask import Flask, request
import requests
import os
import re

app = Flask(__name__)

# 🔐 Токен твого Telegram-бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

# 🔠 Мапи транслітерації для укр та рос
TRANSLIT_UA = {
    'а':'a','б':'b','в':'v','г':'h','ґ':'g','д':'d','е':'e','є':'ye','ж':'zh',
    'з':'z','и':'y','і':'i','ї':'yi','й':'y','к':'k','л':'l','м':'m','н':'n',
    'о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts',
    'ч':'ch','ш':'sh','щ':'shch','ь':'','ю':'yu','я':'ya',
    'А':'a','Б':'b','В':'v','Г':'h','Ґ':'g','Д':'d','Е':'e','Є':'ye','Ж':'zh',
    'З':'z','И':'y','І':'i','Ї':'yi','Й':'y','К':'k','Л':'l','М':'m','Н':'n',
    'О':'o','П':'p','Р':'r','С':'s','Т':'t','У':'u','Ф':'f','Х':'kh','Ц':'ts',
    'Ч':'ch','Ш':'sh','Щ':'shch','Ь':'','Ю':'yu','Я':'ya'
}

TRANSLIT_RU = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z',
    'и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r',
    'с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch',
    'ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
    'А':'a','Б':'b','В':'v','Г':'g','Д':'d','Е':'e','Ё':'yo','Ж':'zh','З':'z',
    'И':'i','Й':'y','К':'k','Л':'l','М':'m','Н':'n','О':'o','П':'p','Р':'r',
    'С':'s','Т':'t','У':'u','Ф':'f','Х':'kh','Ц':'ts','Ч':'ch','Ш':'sh','Щ':'shch',
    'Ъ':'','Ы':'y','Ь':'','Э':'e','Ю':'yu','Я':'ya'
}

def detect_language(text):
    if any(ch in 'ґєіїҐЄІЇ' for ch in text):
        return 'uk'
    elif any(ch in 'ёъыэЁЪЫЭ' for ch in text):
        return 'ru'
    else:
        # за замовчуванням — укр
        return 'uk'

def transliterate(text):
    lang = detect_language(text)
    table = TRANSLIT_UA if lang == 'uk' else TRANSLIT_RU
    result = ''.join(table.get(ch, ch) for ch in text)
    result = re.sub(r'[^a-zA-Z0-9]+', '_', result)
    result = re.sub(r'_+', '_', result).strip('_').lower()
    return result

@app.route('/', methods=['GET'])
def index():
    return "✅ Transliteration bot (UA+RU) is running!"

@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def receive_update():
    update = request.get_json()
    if not update:
        return "No update", 400

    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text")

    if chat_id and text:
        if text.startswith("/start"):
            reply = (
                "👋 Привіт! Я бот для транслітерації 🇺🇦🇷🇺\n"
                "Надішли слово українською або російською — отримаєш версію, "
                "як у пошуку Telegram.\n\n"
                "Наприклад:\nновини → noviny\nкиев → kiev\nпогода україна → pogoda_ukraina"
            )
        else:
            translit = transliterate(text)
            reply = f"🔤 *{text.strip()}* → `{translit}`"

        requests.post(API_URL + "sendMessage", json={
            "chat_id": chat_id,
            "text": reply,
            "parse_mode": "Markdown"
        })

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
