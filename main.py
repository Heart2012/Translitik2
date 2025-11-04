import os
import json
import re
import requests
from flask import Flask, request

# === Налаштування ===
TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN"
CUSTOM_DICT_FILE = "custom_dict.json"
UNKNOWN_FILE = "unknown_words.txt"
SEP = "="  # роздільник для словника, можна змінити

app = Flask(__name__)
user_states = {}  # стан користувачів
custom_map = {}   # словник за категоріями

# === Завантаження словника ===
def load_dict():
    global custom_map
    if os.path.exists(CUSTOM_DICT_FILE):
        with open(CUSTOM_DICT_FILE, "r", encoding="utf-8") as f:
            custom_map = json.load(f)
    else:
        custom_map = {}
load_dict()

# === Невідомі слова/фрази ===
def save_unknown(word):
    word = word.strip().lower()
    if not word:
        return
    existing = set()
    if os.path.exists(UNKNOWN_FILE):
        with open(UNKNOWN_FILE, "r", encoding="utf-8") as f:
            existing = {w.strip().lower() for w in f.readlines()}
    if word not in existing:
        with open(UNKNOWN_FILE, "a", encoding="utf-8") as f:
            f.write(word + "\n")

def remove_unknown(word):
    word = word.strip().lower()
    if not os.path.exists(UNKNOWN_FILE):
        return
    with open(UNKNOWN_FILE, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines()]
    lines = [l for l in lines if l.lower() != word]
    with open(UNKNOWN_FILE, "w", encoding="utf-8") as f:
        for l in lines:
            f.write(l + "\n")

def clear_unknown():
    if os.path.exists(UNKNOWN_FILE):
        open(UNKNOWN_FILE, "w", encoding="utf-8").close()

# === Збереження словника ===
def save_dict():
    with open(CUSTOM_DICT_FILE, "w", encoding="utf-8") as f:
        json.dump(custom_map, f, ensure_ascii=False, indent=2)

# === Транслітерація (Українська) ===
TRANSLIT_UA = {
    "а":"a","б":"b","в":"v","г":"h","ґ":"g","д":"d","е":"e","є":"ie",
    "ж":"zh","з":"z","и":"y","і":"i","ї":"i","й":"i","к":"k","л":"l",
    "м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u",
    "ф":"f","х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"shch","ь":"",
    "ю":"iu","я":"ia"
}
def transliterate(text):
    return "".join(TRANSLIT_UA.get(c.lower(), c) for c in text)

# === Клавіатура ===
def get_main_keyboard():
    keyboard = {
        "keyboard":[
            ["🔤 Транслітерація", "📚 Словник"],
            ["➕ Додати", "✏️ Редагувати", "🗑️ Видалити"],
            ["⬇️ Експорт", "⬆️ Імпорт"],
            ["⚠️ Невідомі слова","📥 Додати невідомі у словник","📤 Скинути всі невідомі"],
            ["📤 Експорт невідомих","📥 Імпорт невідомих"]
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
    requests.post(url, json=payload)

def send_file(chat_id, filename):
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    with open(filename, "rb") as f:
        requests.post(url, data={"chat_id": chat_id}, files={"document": f})

# === Парсинг багаторядкового вводу для словника з категорією ===
# Формат рядка: Категорія Слово=трансліт
def parse_multiline_input_with_category(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    parsed = []
    for line in lines:
        if " " in line and SEP in line:
            cat, rest = line.split(" ",1)
            word, translit_word = rest.split(SEP,1)
            parsed.append((cat.strip(), word.strip().lower(), translit_word.strip()))
    return parsed

# === Перевірка українських літер та апострофу ʼ ===
def has_ukrainian_letters(text):
    return bool(re.search(r"[а-яєіїґА-ЯЄІЇҐʼ]", text))

# === Трансліт рядка з перевіркою словника та склеєних слів ===
def translit_text_line(text):
    lw = text.lower()
    result = ""
    i = 0
    while i < len(lw):
        match = None
        for j in range(len(lw), i, -1):
            part = lw[i:j]
            found = None
            for cat in custom_map:
                if part in custom_map[cat]:
                    found = custom_map[cat][part]
                    break
            if found:
                match = found
                break
        if match:
            result += match
            remove_unknown(part)
            i += len(part)
        else:
            if re.match(r'\w', lw[i]):
                result += f"[{lw[i]}]"
                save_unknown(lw[i])
            else:
                result += lw[i]
            i += 1
    return result

# === Основний вебхук ===
@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    message = update.get("message", {})
    text = message.get("text", "").strip()
    chat_id = message.get("chat", {}).get("id")
    if not chat_id or not text:
        return "No message", 200

    state = user_states.get(chat_id)

    # --- Попередження для українських літер ---
    if text and has_ukrainian_letters(text):
        send_message(chat_id, "⚠️ У тексті є українські літери або апостроф ʼ. Бот виконає транслітерацію з української.", get_main_keyboard())

    # --- Дії кнопок ---
    buttons = {
        "📚 Словник":"list",
        "🔤 Транслітерація":"translit",
        "➕ Додати":"add",
        "✏️ Редагувати":"edit",
        "🗑️ Видалити":"delete",
        "⬇️ Експорт":"export",
        "⬆️ Імпорт":"import",
        "⚠️ Невідомі слова":"unknown",
        "📤 Скинути всі невідомі":"unknown_clear",
        "📥 Додати невідомі у словник":"import_unknown_manual",
        "📤 Експорт невідомих":"unknown_export",
        "📥 Імпорт невідомих":"unknown_import"
    }

    if text in buttons:
        action = buttons[text]

        if action == "list":
            if not custom_map:
                reply = "📭 Словник порожній."
            else:
                reply = ""
                for cat, words in custom_map.items():
                    reply += f"*{cat}*\n"
                    for k,v in words.items():
                        reply += f"{k}{SEP}`{v}`\n"
            send_message(chat_id, reply, get_main_keyboard())
            return "OK",200

        elif action == "translit":
            user_states[chat_id] = {"action":"translit"}
            send_message(chat_id,"Введіть текст для транслітерації (можна багаторядково).", get_main_keyboard())
            return "OK",200

    # --- Обробка станів ---
    if state and text:
        action = state["action"]

        if action in ["add","edit"]:
            pairs = parse_multiline_input_with_category(text)
            reply_lines = []
            for cat, k, v in pairs:
                if cat not in custom_map:
                    custom_map[cat] = {}
                if action=="add" or (action=="edit" and k in custom_map[cat]):
                    custom_map[cat][k]=v
                    remove_unknown(k)
                    reply_lines.append(f"{'✅ Додано' if action=='add' else '✏️ Змінено'}: *{k}*{SEP}`{v}` у категорії *{cat}*")
                else:
                    reply_lines.append(f"⚠️ Слова *{k}* немає в категорії *{cat}*")
            save_dict()
            user_states.pop(chat_id)
            send_message(chat_id,"\n".join(reply_lines),get_main_keyboard())
            return "OK",200

        elif action == "translit":
            lines = text.splitlines()
            result_lines = [translit_text_line(l) for l in lines]
            user_states.pop(chat_id)
            send_message(chat_id,"\n".join(result_lines),get_main_keyboard())
            return "OK",200

    # --- Автоматична транслітерація ---
    result_lines = [translit_text_line(text)]
    send_message(chat_id,"\n".join(result_lines),get_main_keyboard())
    return "OK",200

# === Старт ===
@app.route("/",methods=["GET"])
def index():
    return "✅ Transliteration bot is running!"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",10000)))
