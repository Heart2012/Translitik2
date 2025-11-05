import os
import json
import re
import requests
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN"
PORT = int(os.getenv("PORT", 10000))
CUSTOM_DICT_FILE = "custom_dict.json"
UNKNOWN_FILE = "unknown_words.txt"
SEP = "="  # роздільник для словника

app = Flask(__name__)
user_states = {}  # стан користувачів
custom_map = {}   # словник за категоріями

# --- Завантаження словника ---
def load_dict():
    global custom_map
    if os.path.exists(CUSTOM_DICT_FILE):
        with open(CUSTOM_DICT_FILE, "r", encoding="utf-8") as f:
            custom_map = json.load(f)
    else:
        custom_map = {}
load_dict()

# --- Збереження словника ---
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

# --- Транслітерація (укр) ---
TRANSLIT_UA = {
    "а":"a","б":"b","в":"v","г":"h","ґ":"g","д":"d","е":"e","є":"ie",
    "ж":"zh","з":"z","и":"y","і":"i","ї":"i","й":"i","к":"k","л":"l",
    "м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u",
    "ф":"f","х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"shch","ь":"",
    "ю":"iu","я":"ia"
}

def transliterate(text):
    return "".join(TRANSLIT_UA.get(c.lower(), c) for c in text)

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

def get_category_buttons():
    buttons = []
    for cat in custom_map.keys():
        buttons.append([{"text": cat, "callback_data": f"cat_{cat}"}])
    buttons.append([{"text": "➕ Нова категорія", "callback_data": "cat_new"}])
    return {"inline_keyboard": buttons}

# --- Відправка повідомлень ---
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

# --- Парсинг багаторядкового вводу для словника ---
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

# --- Трансліт рядка з перевіркою словника ---
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

# --- Основний webhook ---
@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()
    if not chat_id or not text:
        return "No message", 200

    state = user_states.get(chat_id)

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
        "📥 Додати невідомі у словник":"import_unknown_manual"
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

        elif action == "import_unknown_manual":
            if not os.path.exists(UNKNOWN_FILE):
                send_message(chat_id,"📭 Немає невідомих слів.",get_main_keyboard())
                user_states.pop(chat_id,None)
                return "OK",200
            with open(UNKNOWN_FILE,"r",encoding="utf-8") as f:
                unknown_words = [l.strip() for l in f if l.strip()]
            if not unknown_words:
                send_message(chat_id,"📭 Немає невідомих слів.",get_main_keyboard())
                user_states.pop(chat_id,None)
                return "OK",200
            user_states[chat_id] = {"action":"import_unknown_category","words":unknown_words}
            send_message(chat_id,"Виберіть категорію для додавання невідомих слів:", get_category_buttons())
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

# --- Callback для категорій ---
@app.route("/callback", methods=["POST"])
def callback():
    update = request.get_json()
    callback = update.get("callback_query", {})
    chat_id = callback.get("message",{}).get("chat",{}).get("id")
    data = callback.get("data","")
    callback_id = callback.get("id","")

    # підтвердження кнопки
    requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery", json={"callback_query_id": callback_id})

    state = user_states.get(chat_id)
    if not state or state.get("action")!="import_unknown_category":
        return "OK",200

    if data=="cat_new":
        user_states[chat_id]["waiting_for_new_cat"]=True
        send_message(chat_id,"Введіть назву нової категорії для додавання невідомих слів:")
    elif data.startswith("cat_"):
        cat_name = data[4:]
        added = 0
        if cat_name not in custom_map:
            custom_map[cat_name] = {}
        for w in state["words"]:
            custom_map[cat_name][w] = transliterate(w)
            remove_unknown(w)
            added +=1
        save_dict()
        send_message(chat_id,f"✅ Додано {added} невідомих слів у категорію *{cat_name}*.", get_main_keyboard())
        user_states.pop(chat_id,None)
    return "OK",200

# --- Старт ---
@app.route("/", methods=["GET"])
def index():
    return "✅ Transliteration bot is running!"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=PORT)
