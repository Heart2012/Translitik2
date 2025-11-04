import os
import json
import requests
from flask import Flask, request

# === Налаштування ===
TOKEN = os.getenv("BOT_TOKEN") or "ТВОЙ_ТОКЕН_ТУТ"
WEBHOOK_URL = f"https://YOUR_RENDER_URL/webhook"
CUSTOM_DICT_FILE = "custom_dict.json"
UNKNOWN_FILE = "unknown_words.txt"

app = Flask(__name__)

print("BOT_TOKEN:", TOKEN)  # Перевірка токена

# === Стан користувачів ===
user_states = {}

# === Завантаження словника ===
def load_dict():
    if os.path.exists(CUSTOM_DICT_FILE):
        with open(CUSTOM_DICT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_dict():
    with open(CUSTOM_DICT_FILE, "w", encoding="utf-8") as f:
        json.dump(custom_map, f, ensure_ascii=False, indent=2)

custom_map = load_dict()

# === Збереження невідомих слів ===
def save_unknown(word):
    word = word.strip().lower()
    if not word:
        return
    if not os.path.exists(UNKNOWN_FILE):
        with open(UNKNOWN_FILE, "w", encoding="utf-8") as f:
            f.write("")
    with open(UNKNOWN_FILE, "r", encoding="utf-8") as f:
        existing = {w.strip().lower() for w in f.readlines()}
    if word not in existing:
        with open(UNKNOWN_FILE, "a", encoding="utf-8") as f:
            f.write(word + "\n")

# === Транслітерація ===
TRANSLIT_UA = {
    "а": "a","б": "b","в": "v","г": "h","ґ": "g","д": "d","е": "e","є": "ie",
    "ж": "zh","з": "z","и": "y","і": "i","ї": "i","й": "i","к": "k","л": "l",
    "м": "m","н": "n","о": "o","п": "p","р": "r","с": "s","т": "t","у": "u",
    "ф": "f","х": "kh","ц": "ts","ч": "ch","ш": "sh","щ": "shch","ь": "",
    "ю": "iu","я": "ia"
}

def transliterate(text):
    return "".join(TRANSLIT_UA.get(c.lower(), c) for c in text)

# === Клавіатура ===
def get_main_keyboard():
    keyboard = {
        "keyboard": [
            ["🔤 Транслітерація", "📚 Словник"],
            ["➕ Додати", "✏️ Редагувати", "🗑️ Видалити"],
            ["⬇️ Експорт", "⬆️ Імпорт"],
            ["⚠️ Невідомі слова", "📥 Імпорт невідомих"]
        ],
        "resize_keyboard": True
    }
    return keyboard

# === Відправка повідомлень ===
def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    r = requests.post(url, json=payload)
    print("send_message response:", r.status_code, r.text)

def send_file(chat_id, filename):
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    with open(filename, "rb") as f:
        r = requests.post(url, data={"chat_id": chat_id}, files={"document": f})
    print("send_file response:", r.status_code, r.text)

# === Обробка багаторядкових даних ===
def parse_multiline_input(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    pairs = []
    for line in lines:
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            pairs.append((parts[0].lower(), parts[1].lower()))
    return pairs

# === Основний обробник вебхука ===
@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    print("Received update:", json.dumps(update, ensure_ascii=False, indent=2))

    message = update.get("message", {})
    text = message.get("text", "").strip()
    chat_id = message.get("chat", {}).get("id")

    if not chat_id or not text:
        return "No message", 200

    state = user_states.get(chat_id)

    # --- Кнопки ---
    if text in ["📚 Словник", "🔤 Транслітерація", "➕ Додати", "✏️ Редагувати",
                "🗑️ Видалити", "⬇️ Експорт", "⬆️ Імпорт",
                "⚠️ Невідомі слова", "📥 Імпорт невідомих"]:
        action_map = {
            "📚 Словник": "list",
            "🔤 Транслітерація": "translit",
            "➕ Додати": "add",
            "✏️ Редагувати": "edit",
            "🗑️ Видалити": "delete",
            "⬇️ Експорт": "export",
            "⬆️ Імпорт": "import",
            "⚠️ Невідомі слова": "unknown",
            "📥 Імпорт невідомих": "unknown_import"
        }
        data = action_map[text]

        if data == "list":
            if custom_map:
                lines = [f"*{k}* → `{v}`" for k,v in custom_map.items()]
                reply = "📚 *Словник:*\n" + "\n".join(lines)
            else:
                reply = "📭 Словник порожній."
            send_message(chat_id, reply, get_main_keyboard())
            return "OK", 200

        elif data == "export":
            if custom_map:
                filename = "custom_export.txt"
                with open(filename, "w", encoding="utf-8") as f:
                    for k,v in custom_map.items():
                        f.write(f"{k} {v}\n")
                send_file(chat_id, filename)
            else:
                send_message(chat_id, "📭 Словник порожній.", get_main_keyboard())
            return "OK", 200

        elif data == "unknown":
            if os.path.exists(UNKNOWN_FILE):
                with open(UNKNOWN_FILE, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                if lines:
                    reply = "⚠️ *Невідомі слова:*\n" + "\n".join(f"• `{w}`" for w in lines)
                    send_message(chat_id, reply, get_main_keyboard())
                else:
                    send_message(chat_id, "✅ Невідомих слів немає.", get_main_keyboard())
            else:
                send_message(chat_id, "✅ Невідомих слів немає.", get_main_keyboard())
            return "OK", 200

        elif data == "unknown_import":
            if os.path.exists(UNKNOWN_FILE):
                with open(UNKNOWN_FILE, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                if lines:
                    filename = "unknown_export.txt"
                    with open(filename, "w", encoding="utf-8") as f:
                        for w in lines:
                            f.write(w + "\n")
                    send_file(chat_id, filename)
                else:
                    send_message(chat_id, "📭 Немає невідомих слів для експорту.", get_main_keyboard())
            else:
                send_message(chat_id, "📭 Немає невідомих слів для експорту.", get_main_keyboard())
            return "OK", 200

        else:
            user_states[chat_id] = {"action": data}
            prompts = {
                "add": "Введіть кілька рядків `слово translit`, кожен з нового рядка:",
                "edit": "Введіть кілька рядків `слово новий_translit`:",
                "delete": "Введіть по одному слову на рядок для видалення:",
                "translit": "Введіть текст (можна кілька рядків) для транслітерації:",
                "import": "📤 Надішліть .txt файл або вставте список `слово translit` рядками."
            }
            send_message(chat_id, prompts[data], get_main_keyboard())
            return "OK", 200

    # --- Обробка станів ---
    if state and text:
        action = state["action"]
        reply = ""
        try:
            if action == "add":
                pairs = parse_multiline_input(text)
                for w,t in pairs:
                    custom_map[w] = t
                save_dict()
                reply = f"✅ Додано {len(pairs)} слів."

            elif action == "edit":
                pairs = parse_multiline_input(text)
