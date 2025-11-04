from flask import Flask, request
import requests
import os
import re

app = Flask(__name__)

# 🔐 Токен твого Telegram-бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

# 🔠 Транслітерація
TRANSLIT_MAP = {
    'а':'a','б':'b','в':'v','г':'h','ґ':'g','д':'d','е':'e','є':'ie','ж':'zh',
    'з':'z','и':'y','і':'i','ї':'i','й':'i','к':'k','л':'l','м':'m','н':'n',
    'о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts',
    'ч':'ch','ш':'sh','щ':'shch','ь':'','ю':'iu','я':'ia',
    'А':'a','Б':'b','В':'v','Г':'h','Ґ':'g','Д':'d','Е':'e','Є':'ie','Ж':'zh',
    'З':'z','И':'y','І':'i','Ї':'i','Й':'i','К':'k','Л':'l','М':'m','Н':'n',
    'О':'o','П':'p','Р':'r','С':'s','Т':'t','У':'u','Ф':'f','Х':'kh','Ц':'ts',
    'Ч':'ch','Ш':'sh','Щ':'shch','Ь':'','Ю':'iu','Я':'ia'
}

def transliterate(text):
    result = ''.join(TRANSLIT_MAP.get(ch, ch) for ch in text)
    result = re.sub(r'[^a-zA-Z0-9]+', '_', result)
    return re.sub(r'_+', '_', result).strip('_').lower()

@app.route('/', methods=['GET'])
def index():
    return "✅ Transliteration bot is running!"

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
                "👋 Привіт! Надішли слово українською — я зроблю транслітерацію, "
                "як у пошуку Telegram.\n\nНаприклад:\nновини → noviny\nкиївські новини → kyivski_novyny"
            )
        else:
            reply = transliterate(text)

        requests.post(API_URL + "sendMessage", json={"chat_id": chat_id, "text": reply})

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
