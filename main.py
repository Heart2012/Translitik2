from flask import Flask, request
import json
import os
import requests

TOKEN = "ТВОЙ_ТОКЕН_ТУТ"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

DICTIONARY_FILE = "dictionary.txt"
UNKNOWN_FILE = "unknown.txt"

# ---------- Функції роботи зі словником ----------

def load_dictionary():
    dictionary = {}
    if os.path.exists(DICTIONARY_FILE):
        with open(DICTIONARY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "//" in line:
                    phrase, translit = line.split("//", 1)
                    dictionary[phrase.strip().lower()] = translit.strip()
    return dictionary


def save_dictionary(dictionary):
    with open(DICTIONARY_FILE, "w", encoding="utf-8") as f:
        for phrase, translit in dictionary.items():
            f.write(f"{phrase}//{translit}\n")


def add_to_unknown(text):
    with open(UNKNOWN_FILE, "a", encoding="utf-8") as f:
        f.write(text.strip() + "\n")


def clear_unknown():
    open(UNKNOWN_FILE, "w", encoding="utf-8").close()


def load_unknown():
    if not os.path.exists(UNKNOWN_FILE):
        return "unknown.txt порожній."
    with open(UNKNOWN_FILE, "r", encoding="utf-8") as f:
        return f.read() or "unknown.txt порожній."

# ---------- Транслітерація ----------

def transliterate_text(text, dictionary):
    result = text
    for phrase, translit in dictionary.items():
        if phrase.lower() in result.lower():
            result = result.replace(phrase, translit)
    # позначення невідомих
    words = text.split()
    for w in words:
        found = False
        for phrase in dictionary.keys():
            if w.lower() in phrase.lower():
                found = True
                break
        if not found and "[" + w + "]" not in result:
            result = result.replace(w, f"[{w}]")
            add_to_unknown(w)
    return result

# ---------- Кнопки ----------

def main_keyboard():
    return {
        "keyboard": [
            [{"text": "📘 Переглянути словник"}, {"text": "➕ Додати фрази"}],
            [{"text": "📤 Експорт словника"}, {"text": "📥 Імпорт словника"}],
            [{"text": "❓ Unknown.txt"}, {"text": "🧹 Очистити Unknown"}],
        ],
        "resize_keyboard": True,
        "persistent": True
    }

# ---------- Telegram логіка ----------

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return "No data"

    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()

        dictionary = load_dictionary()

        if text == "/start":
            send_message(chat_id, "👋 Привіт! Я бот для транслітерації.\nВикористовуй кнопки нижче:", main_keyboard())
        elif text == "📘 Переглянути словник":
            if dictionary:
                dict_text = "\n".join([f"{k} // {v}" for k, v in dictionary.items()])
                send_message(chat_id, f"📘 Словник:\n\n{dict_text}", main_keyboard())
            else:
                send_message(chat_id, "📖 Словник порожній.", main_keyboard())
        elif text == "📤 Експорт словника":
            send_file(chat_id, DICTIONARY_FILE)
        elif text == "📥 Імпорт словника":
            send_message(chat_id, "📥 Надішли мені файл у форматі `фраза//трансліт`, кожна пара з нового рядка.", main_keyboard())
        elif text == "➕ Додати фрази":
            send_message(chat_id, "Введи нові фрази у форматі:\n`фраза // трансліт`\nКожна пара — з нового рядка.", main_keyboard())
        elif text == "❓ Unknown.txt":
            send_message(chat_id, f"🧩 Невідомі фрази:\n\n{load_unknown()}", main_keyboard())
        elif text == "🧹 Очистити Unknown":
            clear_unknown()
            send_message(chat_id, "✅ Файл unknown.txt очищено!", main_keyboard())
        elif "//" in text and "\n" in text:
            # додавання кількох фраз
            added = 0
            for line in text.splitlines():
                if "//" in line:
                    phrase, translit = line.split("//", 1)
                    dictionary[phrase.strip().lower()] = translit.strip()
                    added += 1
            save_dictionary(dictionary)
            send_message(chat_id, f"✅ Додано {added} фраз(и) у словник!", main_keyboard())
        else:
            result = transliterate_text(text, dictionary)
            send_message(chat_id, result, main_keyboard())

    return "OK"

# ---------- Допоміжні функції ----------

def send_message(chat_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard)
    requests.post(f"{BASE_URL}/sendMessage", data=payload)


def send_file(chat_id, file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            requests.post(f"{BASE_URL}/sendDocument", data={"chat_id": chat_id}, files={"document": f})
    else:
        send_message(chat_id, f"Файл {file_path} не знайдено.", main_keyboard())

# ---------- Flask тест ----------

@app.route("/")
def index():
    return "✅ Translit bot працює!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
