import os
from flask import Flask, request
import telebot
from telebot import types

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН_ТУТ")
bot = telebot.TeleBot(BOT_TOKEN)

DICT_FILE = "dictionary.txt"
UNKNOWN_FILE = "unknown.txt"

dictionary = {}


# --- Завантаження словника ---
def load_dictionary():
    dictionary.clear()
    if not os.path.exists(DICT_FILE):
        open(DICT_FILE, "w").close()
    with open(DICT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "//" in line:
                key, val = line.strip().split("//", 1)
                dictionary[key.strip()] = val.strip()


# --- Збереження словника ---
def save_dictionary():
    with open(DICT_FILE, "w", encoding="utf-8") as f:
        for k, v in dictionary.items():
            f.write(f"{k}//{v}\n")


load_dictionary()


# --- Кнопки ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📘 Словник", "➕ Додати", "📤 Експорт", "📥 Імпорт")
    markup.add("📄 Unknown", "🧹 Очистити unknown", "🔄 Перезавантажити словник")
    return markup


# --- Головна логіка ---
@bot.message_handler(commands=["start"])
def start(msg):
    bot.send_message(
        msg.chat.id,
        "👋 Привіт! Я бот для транслітерації.\nВведи фразу, і я заміню все, що знайду в словнику.",
        reply_markup=main_menu()
    )


@bot.message_handler(func=lambda m: True)
def handle_message(msg):
    text = msg.text.strip()

    if text == "📘 Словник":
        if not dictionary:
            bot.send_message(msg.chat.id, "Словник порожній.", reply_markup=main_menu())
        else:
            dict_text = "\n".join([f"{k} // {v}" for k, v in dictionary.items()])
            bot.send_message(msg.chat.id, f"📘 Твій словник:\n\n{dict_text}", reply_markup=main_menu())

    elif text == "📤 Експорт":
        if os.path.exists(DICT_FILE):
            with open(DICT_FILE, "rb") as f:
                bot.send_document(msg.chat.id, f, visible_file_name="dictionary.txt")
        else:
            bot.send_message(msg.chat.id, "Файл словника не знайдено.", reply_markup=main_menu())

    elif text == "📄 Unknown":
        if os.path.exists(UNKNOWN_FILE) and os.path.getsize(UNKNOWN_FILE) > 0:
            with open(UNKNOWN_FILE, "rb") as f:
                bot.send_document(msg.chat.id, f, visible_file_name="unknown.txt")
        else:
            bot.send_message(msg.chat.id, "Файл unknown.txt порожній або не створений.", reply_markup=main_menu())

    elif text == "🧹 Очистити unknown":
        open(UNKNOWN_FILE, "w", encoding="utf-8").close()
        bot.send_message(msg.chat.id, "✅ Файл unknown.txt очищено.", reply_markup=main_menu())

    elif text == "🔄 Перезавантажити словник":
        load_dictionary()
        bot.send_message(msg.chat.id, "🔁 Словник успішно перезавантажено!", reply_markup=main_menu())

    elif text == "➕ Додати":
        bot.send_message(
            msg.chat.id,
            "Відправ нові фрази у форматі:\n<code>фраза // транслітерація</code>\nМожна кілька рядків одразу.",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
        bot.register_next_step_handler(msg, add_entries)

    elif text == "📥 Імпорт":
        bot.send_message(
            msg.chat.id,
            "📎 Надішли .txt файл словника для імпорту (формат: фраза // транслітерація).",
            reply_markup=main_menu()
        )
        bot.register_next_step_handler(msg, import_file)

    else:
        translit_text = apply_translit(text)
        bot.send_message(msg.chat.id, translit_text, reply_markup=main_menu())


# --- Додавання нових записів ---
def add_entries(msg):
    lines = msg.text.strip().split("\n")
    added = 0
    for line in lines:
        if "//" in line:
            k, v = line.split("//", 1)
            dictionary[k.strip()] = v.strip()
            added += 1
    save_dictionary()
    bot.send_message(msg.chat.id, f"✅ Додано {added} фраз(и) до словника.", reply_markup=main_menu())


# --- Імпорт файлу ---
def import_file(msg):
    if not msg.document:
        bot.send_message(msg.chat.id, "❌ Це не файл. Надішли .txt документ.", reply_markup=main_menu())
        return

    file_info = bot.get_file(msg.document.file_id)
    downloaded = bot.download_file(file_info.file_path)
    with open(DICT_FILE, "wb") as f:
        f.write(downloaded)

    load_dictionary()
    bot.send_message(msg.chat.id, "✅ Словник імпортовано!", reply_markup=main_menu())


# --- Транслітерація ---
def apply_translit(text):
    result = text
    unknown_phrases = []

    # заміна фраз зі словника (найдовші — спочатку)
    for phrase in sorted(dictionary.keys(), key=len, reverse=True):
        if phrase in result:
            result = result.replace(phrase, dictionary[phrase])

    # пошук невідомих фраз
    words = text.split()
    for w in words:
        if all(k not in w for k in dictionary.keys()):
            result = result.replace(w, f"[{w}]")
            unknown_phrases.append(w)

    # запис unknown
    if unknown_phrases:
        with open(UNKNOWN_FILE, "a", encoding="utf-8") as f:
            for w in unknown_phrases:
                f.write(w + "\n")

    return result


# --- Flask webhook ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.data.decode("utf-8"))])
    return "OK", 200


@app.route("/")
def index():
    return "Bot is running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
