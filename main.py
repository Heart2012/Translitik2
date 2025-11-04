import os
import json
import requests
from flask import Flask, request

# === Налаштування ===
TOKEN = os.getenv("BOT_TOKEN") or "ТВОЙ_ТОКЕН_ТУТ"
WEBHOOK_URL = f"https://YOUR_RENDER_URL/webhook"
custom_dict_file = "custom_dict.json"
unknown_file = "unknown_words.txt"

app = Flask(__name__)

# === Змінні станів ===
user_states = {}

# === Завантаження словника ===
def load_dict():
    if os.path.exists(custom_dict_file):
        with open(custom_dict_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_dict():
    with open(custom_dict_file, "w", encoding="utf-8") as f:
        json.dump(custom_map, f, ensure_ascii=False, indent=2)

custom_map = load_dict()


# === Збереження невідомих слів ===
def save_unknown(word):
    word = word.strip().lower()
    if not word:
        return
    if not os.path.exists(unknown_file):
        with open(unknown_file, "w", encoding="utf-8") as f:
            f.write("")
    with open(unknown_file, "r", encoding="utf-8") as f:
        existing = {w.strip().lower() for w in f.readlines()}
    if word not in existing:
        with open(unknown_file, "a", encoding="utf-8") as f:
            f.write(word + "\n")


# === Транслітерація (базова, українська → латиниця) ===
def transliterate(text):
    mapping = {
        "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g",
        "д": "d", "е": "e", "є": "ie", "ж": "zh", "з": "z",
        "и": "y", "і": "i", "ї": "i", "й": "i", "к": "k",
        "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
        "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
        "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh",
        "щ": "shch", "ь": "", "ю": "iu", "я": "ia"
    }
    return "".join(mapping.get(c.lower(), c) for c in text)


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
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=payload)


def send_file(chat_id, filename):
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    with open(filename, "rb") as f:
        requests.post(url, data={"chat_id": chat_id}, files={"document": f})


# === Обробка багаторядкових даних ===
def parse_multiline_input(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    pairs = []
    for line in lines:
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            pairs.append((parts[0].lower(), parts[1].lower()))
    return pairs


# === Обробка оновлень ===
@app.route("/webhook", methods=["POST"])
def receive_update():
    update = request.get_json()
    if not update:
        return "No update", 400

    message = update.get("message", {})
    text = message.get("text", "").strip()
    chat_id = message.get("chat", {}).get("id")

    if not chat_id or not text:
        return "No message", 200

    state = user_states.get(chat_id)

    # --- Обробка текстових кнопок ---
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

        # --- Список ---
        if data == "list":
            if custom_map:
                lines = [f"*{k}* → `{v}`" for k, v in custom_map.items()]
                reply = "📚 *Словник:*\n" + "\n".join(lines)
            else:
                reply = "📭 Словник порожній."
            send_message(chat_id, reply, reply_markup=get_main_keyboard())
            return "OK", 200

        # --- Експорт ---
        elif data == "export":
            if custom_map:
                filename = "custom_export.txt"
                with open(filename, "w", encoding="utf-8") as f:
                    for k, v in custom_map.items():
                        f.write(f"{k} {v}\n")
                send_file(chat_id, filename)
            else:
                send_message(chat_id, "📭 Словник порожній.", reply_markup=get_main_keyboard())
            return "OK", 200

        # --- Невідомі слова ---
        elif data == "unknown":
            if os.path.exists(unknown_file):
                with open(unknown_file, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                if lines:
                    reply = "⚠️ *Невідомі слова:*\n" + "\n".join(f"• `{w}`" for w in lines)
                    send_message(chat_id, reply, reply_markup=get_main_keyboard())
                else:
                    send_message(chat_id, "✅ Невідомих слів немає.", reply_markup=get_main_keyboard())
            else:
                send_message(chat_id, "✅ Невідомих слів немає.", reply_markup=get_main_keyboard())
            return "OK", 200

        # --- Імпорт невідомих ---
        elif data == "unknown_import":
            if os.path.exists(unknown_file):
                with open(unknown_file, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                if lines:
                    filename = "unknown_export.txt"
                    with open(filename, "w", encoding="utf-8") as f:
                        for w in lines:
                            f.write(w + "\n")
                    send_file(chat_id, filename)
                else:
                    send_message(chat_id, "📭 Немає невідомих слів для експорту.", reply_markup=get_main_keyboard())
            else:
                send_message(chat_id, "📭 Немає невідомих слів для експорту.", reply_markup=get_main_keyboard())
            return "OK", 200

        # --- Решта дій ---
        else:
            user_states[chat_id] = {"action": data}
            prompts = {
                "add": "Введіть кілька рядків `слово translit`, кожен з нового рядка:",
                "edit": "Введіть кілька рядків `слово новий_translit`:",
                "delete": "Введіть по одному слову на рядок для видалення:",
                "translit": "Введіть текст (можна кілька рядків) для транслітерації:",
                "import": "📤 Надішліть .txt файл або вставте список `слово translit` рядками."
            }
            send_message(chat_id, prompts[data], reply_markup=get_main_keyboard())
            return "OK", 200

    # --- Обробка станів ---
    if state and text:
        action = state["action"]
        reply = ""

        try:
            if action == "add":
                pairs = parse_multiline_input(text)
                for w, t in pairs:
                    custom_map[w] = t
                save_dict()
                reply = f"✅ Додано {len(pairs)} слів."

            elif action == "edit":
                pairs = parse_multiline_input(text)
                edited = 0
                for w, t in pairs:
                    if w in custom_map:
                        custom_map[w] = t
                        edited += 1
                save_dict()
                reply = f"✏️ Змінено {edited} слів."

            elif action == "delete":
                lines = [l.strip().lower() for l in text.splitlines() if l.strip()]
                deleted = 0
                for w in lines:
                    if w in custom_map:
                        del custom_map[w]
                        deleted += 1
                save_dict()
                reply = f"🗑️ Видалено {deleted} слів."

            elif action == "translit":
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                results = []
                for line in lines:
                    words = line.split()
                    result_words = []
                    for w in words:
                        lw = w.lower()
                        if lw in custom_map:
                            result_words.append(custom_map[lw])
                        else:
                            save_unknown(lw)
                            result_words.append(f"⚠️{transliterate(w)}⚠️")
                    results.append("_".join(result_words))
                reply = "🔤 Результат:\n" + "\n".join(results)

        except Exception as e:
            reply = f"⚠️ Помилка: {e}"

        user_states.pop(chat_id, None)
        send_message(chat_id, reply, reply_markup=get_main_keyboard())
        return "OK", 200

    return "OK", 200


# === Встановлення вебхука ===
@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}"
    r = requests.get(url)
    return r.text


@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
