import os
import json
import re
import requests
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN"
PORT = int(os.getenv("PORT", 10000))
CUSTOM_DICT_FILE = "custom_dict.json"
UNKNOWN_FILE = "unknown_words.txt"
SEP = "="

app = Flask(__name__)
user_states = {}
custom_map = {}  # {category: {word: translit}}

# --- Завантаження словника ---
if os.path.exists(CUSTOM_DICT_FILE):
    with open(CUSTOM_DICT_FILE, "r", encoding="utf-8") as f:
        custom_map = json.load(f)
else:
    custom_map = {}

def save_dict():
    with open(CUSTOM_DICT_FILE, "w", encoding="utf-8") as f:
        json.dump(custom_map, f, ensure_ascii=False, indent=2)

# --- Невідомі слова ---
def save_unknown(word):
    word = word.strip().lower()
    if not word:
        return
    existing = set()
    if os.path.exists(UNKNOWN_FILE):
        with open(UNKNOWN_FILE, "r", encoding="utf-8") as f:
            existing = {l.strip().lower() for l in f}
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

# --- Транслітерація ---
TRANSLIT_UA = {
    "а":"a","б":"b","в":"v","г":"h","ґ":"g","д":"d","е":"e","є":"ie",
    "ж":"zh","з":"z","и":"y","і":"i","ї":"i","й":"i","к":"k","л":"l",
    "м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u",
    "ф":"f","х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"shch","ь":"",
    "ю":"iu","я":"ia"
}

TRANSLIT_RU = {
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"yo","ж":"zh",
    "з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o",
    "п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"kh","ц":"ts",
    "ч":"ch","ш":"sh","щ":"shch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"
}

def detect_language(word):
    if any(ch in "ґєіїҐЄІЇ" for ch in word):
        return "ua"
    elif any(ch in "ёъыэЁЪЫЭ" for ch in word):
        return "ru"
    else:
        return "ua"

def transliterate_word(word):
    lang = detect_language(word)
    table = TRANSLIT_UA if lang=="ua" else TRANSLIT_RU
    return "".join(table.get(c.lower(), c) for c in word)

# --- Клавіатура ---
def get_main_keyboard():
    keyboard = {
        "keyboard":[
            ["🔤 Транслітерація", "📚 Словник"],
            ["➕ Додати", "✏️ Редагувати", "🗑️ Видалити"],
            ["⬇️ Експорт", "⬆️ Імпорт"],
            ["⚠️ Невідомі слова","📥 Додати невідомі у словник","📤 Скинути всі невідомі"]
        ],
        "resize_keyboard": True
    }
    return keyboard

# --- Відправка ---
def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(url, json=payload)

# --- Трансліт по словах ---
def translit_text_line(text):
    words = re.findall(r'\w+|\W+', text)
    result = ""
    for w in words:
        lw = w.lower()
        if re.match(r'\w', w):
            found = None
            for cat in custom_map:
                if lw in custom_map[cat]:
                    found = custom_map[cat][lw]
                    break
            if found:
                result += found
                remove_unknown(lw)
            else:
                auto_translit = transliterate_word(w)
                result += f"[{auto_translit}]"
                save_unknown(lw)
        else:
            result += w
    return result

# --- Webhook ---
@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()
    if not chat_id or not text:
        return "OK",200

    state = user_states.get(chat_id)
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
        "📥 Додати невідомі у словник":"import_unknown_manual"
    }

    # --- Кнопки ---
    if text in buttons:
        action = buttons[text]

        # --- Перегляд словника ---
        if action=="list":
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

        # --- Транслітерація ---
        elif action=="translit":
            user_states[chat_id]={"action":"translit"}
            send_message(chat_id,"Введіть текст для транслітерації (можна багаторядково).",get_main_keyboard())
            return "OK",200

        # --- Додавання слів ---
        elif action=="add":
            user_states[chat_id]={"action":"add_waiting_text"}
            send_message(chat_id,"Введіть слова для додавання (багаторядково, формат: Слово або Слово=трансліт):",get_main_keyboard())
            return "OK",200

        # --- Додавання невідомих ---
        elif action=="import_unknown_manual":
            if not os.path.exists(UNKNOWN_FILE):
                send_message(chat_id,"📭 Немає невідомих слів.",get_main_keyboard())
                return "OK",200
            with open(UNKNOWN_FILE,"r",encoding="utf-8") as f:
                unknown_words=[l.strip() for l in f if l.strip()]
            if not unknown_words:
                send_message(chat_id,"📭 Немає невідомих слів.",get_main_keyboard())
                return "OK",200
            user_states[chat_id]={"action":"import_unknown_category","words":unknown_words}
            send_message(chat_id,"Введіть назву категорії для невідомих слів:",get_main_keyboard())
            return "OK",200

        # --- Скидання невідомих ---
        elif action=="unknown_clear":
            clear_unknown()
            send_message(chat_id,"✅ Скинуто всі невідомі слова.",get_main_keyboard())
            return "OK",200

    # --- Обробка станів ---
    if state and text:
        action = state["action"]

        # --- Трансліт ---
        if action=="translit":
            lines = text.splitlines()
            result_lines=[translit_text_line(l) for l in lines]
            user_states.pop(chat_id)
            send_message(chat_id,"\n".join(result_lines),get_main_keyboard())
            return "OK",200

        # --- Додавання слів ---
        elif action=="add_waiting_text":
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            pending_manual = []
            user_states[chat_id]["pending"] = []
            for line in lines:
                if SEP in line:
                    word, translit_word = line.split(SEP,1)
                    user_states[chat_id]["pending"].append((word.strip().lower(), translit_word.strip()))
                else:
                    pending_manual.append(line.strip())
            if pending_manual:
                user_states[chat_id]["manual_queue"] = pending_manual
                user_states[chat_id]["action"] = "add_manual_translit"
                next_word = pending_manual.pop(0)
                send_message(chat_id,f"Введіть трансліт для слова: *{next_word}*")
            else:
                cat="default"
                if cat not in custom_map:
                    custom_map[cat]={}
                for word,translit_word in user_states[chat_id]["pending"]:
                    custom_map[cat][word]=translit_word
                    remove_unknown(word)
                save_dict()
                user_states.pop(chat_id)
                send_message(chat_id,"✅ Додано слова у словник.",get_main_keyboard())
            return "OK",200

        elif action=="add_manual_translit":
            cat="default"
            if cat not in custom_map:
                custom_map[cat]={}
            word = user_states[chat_id]["manual_queue"][0] if "manual_queue" in user_states[chat_id] else None
            if word:
                custom_map[cat][word]=text.strip()
                remove_unknown(word)
                user_states[chat_id]["manual_queue"].pop(0)
                if user_states[chat_id]["manual_queue"]:
                    next_word=user_states[chat_id]["manual_queue"][0]
                    send_message(chat_id,f"Введіть трансліт для слова: *{next_word}*")
                else:
                    # Додати pending
                    for w,tw in user_states[chat_id].get("pending",[]):
                        custom_map[cat][w]=tw
                        remove_unknown(w)
                    save_dict()
                    user_states.pop(chat_id)
                    send_message(chat_id,"✅ Додано слова у словник.",get_main_keyboard())
            return "OK",200

        elif action=="import_unknown_category":
            cat = text.strip()
            if cat not in custom_map:
                custom_map[cat]={}
            for w in state["words"]:
                custom_map[cat][w]=transliterate_word(w)
                remove_unknown(w)
            save_dict()
            user_states.pop(chat_id)
            send_message(chat_id,f"✅ Додано {len(state['words'])} слів у категорію *{cat}*",get_main_keyboard())
            return "OK",200

    return "OK",200

@app.route("/", methods=["GET"])
def index():
    return "✅ Bot is running"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=PORT)
