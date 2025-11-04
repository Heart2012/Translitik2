from flask import Flask, request
import requests
import os
import json
import re

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"
CUSTOM_FILE = "custom.json"

# 🔹 Завантажуємо або створюємо словник користувацьких транслітерацій
if os.path.exists(CUSTOM_FILE):
    with open(CUSTOM_FILE, "r", encoding="utf-8") as f:
        custom_map = json.load(f)
else:
    custom_map = {}

# 🔠 Мапи транслітерації
TRANSLIT_UA = {'а':'a','б':'b','в':'v','г':'h','ґ':'g','д':'d','е':'e','є':'ye','ж':'zh',
'з':'z','и':'y','і':'i','ї':'yi','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p',
'р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch',
'ь':'','ю':'yu','я':'ya'}
TRANSLIT_RU = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z',
'и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t',
'у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'',
'э':'e','ю':'yu','я':'ya'}

def detect_language(text):
    if any(ch in 'ґєіїҐЄІЇ' for ch in text):
        return 'uk'
    elif any(ch in 'ёъыэЁЪЫЭ' for ch in text):
        return 'ru'
    else:
        return 'uk'

def transliterate(text):
    lang = detect_language(text)
    table = TRANSLIT_UA if lang == 'uk' else TRANSLIT_RU
    result = ''.join(table.get(ch, ch) for ch in text)
    result = re.sub(r'[^a-zA-Z0-9]+', '_', result)
    return re.sub(r'_+', '_', result).strip('_').lower()

@app.route('/', methods=['GET'])
def index():
    return "✅ Transliteration bot (UA+RU+custom) is running!"

@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def receive_update():
    update = request.get_json()
    if not update:
        return "No update", 400

    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()

    if chat_id and text:
        if text.startswith("/start"):
            reply = (
                "👋 Привіт! Я бот для транслітерації 🇺🇦🇷🇺\n"
                "Надішли слово українською або російською — я зроблю його транслітерацію.\n\n"
                "📝 Щоб додати власний варіант:\n`/add слово translit`\n"
                "Приклад:\n`/add київ kyiv`"
            )
        elif text.startswith("/add "):
            try:
                parts = text.split(maxsplit=2)
                orig = parts[1].lower()
                trans = parts[2].lower()
                custom_map[orig] = trans
                with open(CUSTOM_FILE, "w", encoding="utf-8") as f:
                    json.dump(custom_map, f, ensure_ascii=False, indent=2)
                reply = f"✅ Додано: *{orig}* → `{trans}`"
            except Exception:
                reply = "⚠️ Формат команди: `/add слово translit`"
        else:
            key = text.lower()
            if key in custom_map:
                translit = custom_map[key]
                source = "📘 З твого словника"
            else:
                translit = transliterate(text)
                source = "🤖 Автоматична транслітерація"
            search_url = f"https://t.me/s/{translit}"
            reply = (
                f"🔤 *{text}* → `{translit}`\n"
                f"{source}\n\n"
                f"🔗 [Пошук у Telegram]({search_url})"
            )

        requests.post(API_URL + "sendMessage", json={
            "chat_id": chat_id,
            "text": reply,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        })

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
