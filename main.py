from flask import Flask, request
import requests, os, json, re, threading

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"
CUSTOM_FILE = "custom.json"

# --- Завантаження словника ---
if os.path.exists(CUSTOM_FILE):
    with open(CUSTOM_FILE, "r", encoding="utf-8") as f:
        custom_map = json.load(f)
else:
    custom_map = {}

# --- Стан користувачів ---
user_states = {}

# --- Транслітерація ---
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

def save_dict():
    with open(CUSTOM_FILE, "w", encoding="utf-8") as f:
        json.dump(custom_map, f, ensure_ascii=False, indent=2)

# --- Асинхронна відправка ---
def async_send(url, payload=None, files=None):
    def task():
        try:
            if files:
                requests.post(url, data=payload, files=files)
            else:
                requests.post(url, json=payload)
        except Exception as e:
            print("Error sending message:", e)
    threading.Thread(target=task).start()

def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    async_send(API_URL + "sendMessage", payload)

def send_file(chat_id, filename):
    with open(filename, "rb") as f:
        async_send(f"{API_URL}sendDocument", payload={"chat_id": chat_id}, files={"document": f})

def get_main_keyboard():
    keyboard = {
        "inline_keyboard": [
            [{"text": "📚 Переглянути словник", "callback_data": "list"}],
            [{"text": "➕ Додати слово", "callback_data": "add"}],
            [{"text": "✏️ Редагувати слово", "callback_data": "edit"}],
            [{"text": "🗑️ Видалити слово", "callback_data": "delete"}],
            [{"text": "🔤 Транслітерувати текст", "callback_data": "translit"}],
            [{"text": "⬇️ Експорт словника", "callback_data": "export"}],
            [{"text": "⬆️ Імпорт словника", "callback_data": "import"}]
        ]
    }
    return keyboard

@app.route('/', methods=['GET'])
def index():
    return "✅ Transliteration bot is running!"

@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def receive_update():
    update = request.get_json()
    if not update:
        return "No update", 400

    print("Received update:", update)

    # --- Callback кнопки ---
    if "callback_query" in update:
        callback = update["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        data = callback["data"]
        callback_id = callback["id"]

        # Підтвердження кнопки
        async_send(API_URL + "answerCallbackQuery", {"callback_query_id": callback_id})

        if data == "list":
            if custom_map:
                lines = [f"*{k}* → `{v}`" for k,v in custom_map.items()]
                reply = "📚 Словник:\n" + "\n".join(lines)
            else:
                reply = "📭 Словник порожній"
            send_message(chat_id, reply)
        elif data == "export":
            if custom_map:
                filename = "custom_export.txt"
                with open(filename, "w", encoding="utf-8") as f:
                    for k,v in custom_map.items():
                        f.write(f"{k} {v}\n")
                send_file(chat_id, filename)
            else:
                send_message(chat_id, "📭 Словник порожній")
        else:
            user_states[chat_id] = {"action": data, "data": {}}
            action_text = {
                "add": "Введіть слово та його транслітерацію через пробіл, наприклад:\n`київ kyiv`",
                "edit": "Введіть слово та нову транслітерацію через пробіл, наприклад:\n`київ kyiv_new`",
                "delete": "Введіть слово, яке бажаєте видалити",
                "translit": "Введіть текст для транслітерації",
                "import": "📤 Надішліть текстовий файл (.txt) зі словником. Формат: `слово translit` на рядок."
            }
            send_message(chat_id, action_text.get(data, "Введіть дані для дії"))
        return "OK", 200

    # --- Текстові повідомлення ---
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip() if "text" in message else None

    if not chat_id or not (text or "document" in message):
        return "No text", 200

    if text and text.startswith("/start"):
        send_message(chat_id, "👋 Привіт! Використовуй кнопки для керування словником або надішли слово для транслітерації.", reply_markup=get_main_keyboard())
        return "OK", 200

    state = user_states.get(chat_id)

    # --- Імпорт файлу ---
    if "document" in message and state and state["action"] == "import":
        file_id = message["document"]["file_id"]
        file_info = requests.get(f"{API_URL}getFile?file_id={file_id}").json()
        file_path = file_info["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        r = requests.get(file_url)
        content = r.content.decode("utf-8")
        added = 0
        for line in content.splitlines():
            if line.strip():
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    custom_map[parts[0].lower()] = parts[1].lower()
                    added += 1
        save_dict()
        user_states.pop(chat_id, None)
        send_message(chat_id, f"✅ Імпортовано {added} слів зі словника")
        return "OK", 200

    # --- Обробка станів ---
    if state and text:
        action = state["action"]
        reply = ""

        try:
            if action == "add":
                word, translit_word = text.split(maxsplit=1)
                custom_map[word.lower()] = translit_word.lower()
                save_dict()
                reply = f"✅ Додано: *{word}* → `{translit_word}`"

            elif action == "edit":
                word, translit_word = text.split(maxsplit=1)
                key = word.lower()
                if key in custom_map:
                    custom_map[key] = translit_word.lower()
                    save_dict()
                    reply = f"✏️ Змінено: *{word}* → `{translit_word}`"
                else:
                    reply = f"⚠️ Слова *{word}* немає в словнику"

            elif action == "delete":
                key = text.lower()
                if key in custom_map:
                    del custom_map[key]
                    save_dict()
                    reply = f"🗑️ Видалено слово *{text}*"
                else:
                    reply = f"⚠️ Слова *{text}* немає в словнику"

            elif action == "translit":
                words = text.split()
                result_words = []
                for w in words:
                    lw = w.lower()
                    if lw in custom_map:
                        result_words.append(custom_map[lw])
                    else:
                        result_words.append(transliterate(w))
                translit_text = "_".join(result_words)
                reply = f"🔤 {text} → `{translit_text}`"
        except Exception:
            reply = "⚠️ Сталася помилка. Перевірте формат введення."

        user_states.pop(chat_id, None)
        send_message(chat_id, reply)
        return "OK", 200

    # --- Автоматична транслітерація ---
    if text:
        key = text.lower()
        if key in custom_map:
            translit = custom_map[key]
            source = "📘 З твого словника"
        else:
            translit = transliterate(text)
            source = "🤖 Автоматична транслітерація"
        search_url = f"https://t.me/s/{translit}"
        reply = f"🔤 *{text}* → `{translit}`\n{source}\n\n🔗 [Пошук у Telegram]({search_url})"
        send_message(chat_id, reply)

    return "OK", 200

if __name__ == "__main__":
    # ✅ Важливо: дві закриваючі дужки!
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
