import os
import json
from flask import Flask, request
import requests

TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBHOOK_URL = f"https://translitik2-1.onrender.com/{TOKEN}"

app = Flask(__name__)

DICT_FILE = "dictionary.txt"
UNKNOWN_FILE = "unknown.txt"

user_states = {}
custom_map = {}

# --- Завантаження словника ---
def load_dict():
    if os.path.exists(DICT_FILE):
        with open(DICT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if "//" in line:
                    key, val = line.strip().split("//", 1)
                    custom_map[key.lower()] = val
    print(f"Loaded {len(custom_map)} entries")

def save_dict():
    with open(DICT_FILE, "w", encoding="utf-8") as f:
        for k, v in custom_map.items():
            f.write(f"{k}//{v}\n")

# --- Запис unknown ---
def save_unknown(text):
    text = text.strip()
    if not text:
        return
    known = set()
    if os.path.exists(UNKNOWN_FILE):
        with open(UNKNOWN_FILE, "r", encoding="utf-8") as f:
            known = set(f.read().splitlines())
    if text not in known:
        with open(UNKNOWN_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")

# --- Відправка повідомлення ---
def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps(reply_markup) if reply_markup else None,
    }
    requests.post(url, data=data)

# --- Головне меню ---
def main_keyboard():
    return {
        "keyboard": [
            [{"text": "🔤 Транслітерувати"}],
            [{"text": "📘 Подивитись словник"}, {"text": "💾 Завантажити словник"}],
            [{"text": "➕ Додати"}, {"text": "✏️ Редагувати"}, {"text": "🗑️ Видалити"}],
            [{"text": "❓ Невідомі слова"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json()
    print(update)

    if "message" not in update:
        return "OK", 200

    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    # --- Перевірка на кнопки ---
    if text == "/start":
        send_message(chat_id, "Привіт! 👋 Це бот для транслітерації.\nВикористовуй меню нижче 👇", reply_markup=main_keyboard())
        return "OK", 200

    if text == "📘 Подивитись словник":
        if not custom_map:
            send_message(chat_id, "📖 Словник порожній.", reply_markup=main_keyboard())
        else:
            lines = [f"{k}//{v}" for k, v in custom_map.items()]
            chunk = "\n".join(lines[:1000])
            send_message(chat_id, f"📘 *Твій словник:*\n{chunk}", reply_markup=main_keyboard())
        return "OK", 200

    if text == "💾 Завантажити словник":
        if os.path.exists(DICT_FILE):
            url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
            with open(DICT_FILE, "rb") as f:
                requests.post(url, data={"chat_id": chat_id}, files={"document": f})
        else:
            send_message(chat_id, "⚠️ Словник ще не створено.", reply_markup=main_keyboard())
        return "OK", 200

    if text == "❓ Невідомі слова":
        if os.path.exists(UNKNOWN_FILE):
            url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
            with open(UNKNOWN_FILE, "rb") as f:
                requests.post(url, data={"chat_id": chat_id}, files={"document": f})
        else:
            send_message(chat_id, "Невідомих слів поки що немає ✅", reply_markup=main_keyboard())
        return "OK", 200

    if text == "➕ Додати":
        user_states[chat_id] = {"action": "add"}
        send_message(chat_id, "Надішли фрази у форматі:\n`фраза//трансліт`\n(кілька рядків дозволено)", reply_markup=main_keyboard())
        return "OK", 200

    if text == "✏️ Редагувати":
        user_states[chat_id] = {"action": "edit"}
        send_message(chat_id, "Надішли фрази для редагування у форматі:\n`фраза//новий_трансліт`", reply_markup=main_keyboard())
        return "OK", 200

    if text == "🗑️ Видалити":
        user_states[chat_id] = {"action": "delete"}
        send_message(chat_id, "Надішли фрази для видалення (по одній у рядку)", reply_markup=main_keyboard())
        return "OK", 200

    if text == "🔤 Транслітерувати":
        user_states[chat_id] = {"action": "translit"}
        send_message(chat_id, "Введи фразу або кілька рядків для транслітерації:", reply_markup=main_keyboard())
        return "OK", 200

    # --- Обробка станів ---
    if chat_id in user_states:
        state = user_states.pop(chat_id)
        action = state["action"]
        reply = ""

        try:
            if action == "add":
                lines = text.strip().splitlines()
                added = []
                for line in lines:
                    if "//" in line:
                        key, val = line.strip().split("//", 1)
                        custom_map[key.lower()] = val.strip()
                        added.append(f"{key} → {val}")
                save_dict()
                reply = "✅ Додано:\n" + "\n".join(added) if added else "⚠️ Нічого не додано."

            elif action == "edit":
                lines = text.strip().splitlines()
                edited = []
                for line in lines:
                    if "//" in line:
                        key, val = line.strip().split("//", 1)
                        if key.lower() in custom_map:
                            custom_map[key.lower()] = val.strip()
                            edited.append(f"{key} → {val}")
                save_dict()
                reply = "✏️ Змінено:\n" + "\n".join(edited) if edited else "⚠️ Нічого не змінено."

            elif action == "delete":
                lines = text.strip().splitlines()
                deleted = []
                for line in lines:
                    key = line.strip().lower()
                    if key in custom_map:
                        del custom_map[key]
                        deleted.append(key)
                save_dict()
                reply = "🗑️ Видалено:\n" + "\n".join(deleted) if deleted else "⚠️ Нічого не видалено."

            elif action == "translit":
                lines = text.strip().splitlines()
                result_lines = []
                for line in lines:
                    line_l = line.lower()
                    if line_l in custom_map:
                        result_lines.append(custom_map[line_l])
                    else:
                        result_lines.append(f"[{line}]")
                        save_unknown(line)
                reply = "🔤 Результат:\n" + "\n".join(result_lines)

        except Exception as e:
            print("Error:", e)
            reply = "⚠️ Помилка у форматі введення."

        send_message(chat_id, reply, reply_markup=main_keyboard())
        return "OK", 200

    send_message(chat_id, "❓ Не розумію команду. Використовуй меню 👇", reply_markup=main_keyboard())
    return "OK", 200


@app.route("/", methods=["GET"])
def index():
    return "Translit bot is running!", 200


if __name__ == "__main__":
    load_dict()
    app.run(host="0.0.0.0", port=10000)
