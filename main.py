from flask import Flask, request
import requests
import os
import json
import re

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"
CUSTOM_FILE = "custom.json"
TEXT_FILE = "custom.txt"

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

def export_to_txt():
    """Експортує транслітераційний словник у .txt файл."""
    with open(TEXT_FILE, "w", encoding="utf-8") as f:
        for word, translit in custom_map.items():
            f.write(f"{word} -> {translit}\n")

def import_from_txt():
    """Імпортує транслітераційний словник з .txt файлу."""
    if os.path.exists(TEXT_FILE):
        with open(TEXT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if '->' in line:
                    word, translit = line.split('->')
                    custom_map[word.strip()] = translit.strip()
        with open(CUSTOM_FILE, "w", encoding="utf-8") as f:
            json.dump(custom_map, f, ensure_ascii=False, indent=2)

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
                "Приклад:\n`/add київ kyiv`\n\n"
                "🔄 Щоб змінити транслітерацію слова:\n`/update старе_слово нове_трансліт`\n"
                "🗑 Щоб видалити слово: `/remove слово`\n\n"
                "📜 Щоб побачити збережені пари слів, скористайся командою `/list`.\n"
                "💾 Щоб експортувати словник у .txt файл, використовуйте команду `/export`.\n"
                "📥 Для імпорту з .txt файлу — `/import`."
            )
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "Додати слово", "callback_data": "add"}],
                    [{"text": "Переглянути пари", "callback_data": "list"}],
                    [{"text": "Експортувати словник", "callback_data": "export"}],
                    [{"text": "Імпортувати словник", "callback_data": "import"}],
                ]
            }
        elif text.startswith("/add "):
            try:
                parts = text.split(maxsplit=2)
                orig = parts[1].lower()
                trans = parts[2].lower()
                custom_map[orig] = trans
                with open(CUSTOM_FILE, "w", encoding="utf-8") as f:
                    json.dump(custom_map, f, ensure_ascii=False, indent=2)
                reply = f"✅ Додано: *{orig}* → `{trans}`"
                reply_markup = None
            except Exception:
                reply = "⚠️ Формат команди: `/add слово translit`"
                reply_markup = None
        elif text.startswith("/remove "):
            word_to_remove = text.split(maxsplit=1)[1].lower()
            if word_to_remove in custom_map:
                del custom_map[word_to_remove]
                with open(CUSTOM_FILE, "w", encoding="utf-8") as f:
                    json.dump(custom_map, f, ensure_ascii=False, indent=2)
                reply = f"✅ Слово *{word_to_remove}* було видалено."
            else:
                reply = "❌ Це слово не знайдено у словнику."
            reply_markup = None
        elif text.startswith("/update "):
            parts = text.split(maxsplit=2)
            old_word = parts[1].lower()
            new_translit = parts[2].lower()
            if old_word in custom_map:
                custom_map[old_word] = new_translit
                with open(CUSTOM_FILE, "w", encoding="utf-8") as f:
                    json.dump(custom_map, f, ensure_ascii=False, indent=2)
                reply = f"✅ Слово *{old_word}* оновлено на `{new_translit}`."
            else:
                reply = "❌ Це слово не знайдено у словнику."
            reply_markup = None
        elif text.startswith("/list"):
            if custom_map:
                reply = "💾 Ось усі збережені пари:\n\n"
                for word, translit in custom_map.items():
                    reply += f"*{word}* → `{translit}`\n"
            else:
                reply = "❌ Немає жодних збережених пар транслітерацій."
            reply_markup = None
        elif text.startswith("/export"):
            export_to_txt()
            reply = "💾 Словник експортувано в .txt файл!"
            reply_markup = None
        elif text.startswith("/import"):
            import_from_txt()
            reply = "📥 Словник імпортовано з .txt файлу!"
            reply_markup = None
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
            reply_markup = None

        requests.post(API_URL + "sendMessage", json={
            "chat_id": chat_id,
            "text": reply,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
            "reply_markup": reply_markup
        })

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
