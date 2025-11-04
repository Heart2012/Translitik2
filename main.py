import os
import json
import re
import requests
from flask import Flask, request

# === Налаштування ===
TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN"
CUSTOM_DICT_FILE = "custom_dict.json"
UNKNOWN_FILE = "unknown_words.txt"
SEP = "="  # роздільник для словника, можна змінити на ":" або "->"

app = Flask(__name__)
user_states = {}  # стан користувачів
custom_map = {}

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

# === Парсинг багаторядкового вводу для словника ===
def parse_multiline_input(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    pairs = []
    for line in lines:
        if SEP in line:
            parts = line.split(SEP,1)
            pairs.append((parts[0].strip().lower(), parts[1].strip()))
    return pairs

# === Трансліт рядка по словах з перевіркою словника ===
def translit_text_line(text):
    result_words = []
    parts = re.findall(r'\w+|[^\w\s]', text, re.UNICODE)  # слова + роздільники

    for w in parts:
        lw = w.lower()
        if lw in custom_map:
            translit_word = custom_map[lw]
            remove_unknown(lw)
        elif re.match(r'\w+', w):  # слова
            translit_word = f"[{transliterate(w)}]"
            save_unknown(w)
        else:  # роздільники залишаємо
            translit_word = w
        result_words.append(translit_word)

    return "".join(result_words)

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

    # --- Кнопки ---
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

        # --- Дії кнопок ---
        if action == "list":
            reply = "📚 *Словник:*\n" + "\n".join(f"*{k}*{SEP}`{v}`" for k,v in custom_map.items()) if custom_map else "📭 Словник порожній."
            send_message(chat_id, reply, get_main_keyboard())
            return "OK",200

        elif action == "export":
            if custom_map:
                filename = "custom_export.txt"
                with open(filename,"w",encoding="utf-8") as f:
                    for k,v in custom_map.items():
                        f.write(f"{k}{SEP}{v}\n")
                send_file(chat_id, filename)
            else:
                send_message(chat_id,"📭 Словник порожній.",get_main_keyboard())
            return "OK",200

        elif action == "unknown":
            if os.path.exists(UNKNOWN_FILE):
                with open(UNKNOWN_FILE,"r",encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                reply = "⚠️ *Невідомі слова:*\n" + "\n".join(f"[{w}]" for w in lines) if lines else "✅ Невідомих слів немає."
            else:
                reply = "✅ Невідомих слів немає."
            send_message(chat_id,reply,get_main_keyboard())
            return "OK",200

        elif action == "unknown_clear":
            clear_unknown()
            send_message(chat_id,"✅ Список невідомих слів очищено.",get_main_keyboard())
            return "OK",200

        elif action == "import_unknown_manual":
            if os.path.exists(UNKNOWN_FILE):
                with open(UNKNOWN_FILE,"r",encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                if lines:
                    example = "\n".join([f"{w}{SEP}{transliterate(w)}" for w in lines])
                    send_message(chat_id,"Вставте ручну транслітерацію або підтвердіть авто, відправивши:\n"+example,get_main_keyboard())
                    user_states[chat_id]={"action":"import_unknown_manual","data":{"lines":lines}}
            else:
                send_message(chat_id,"⚠️ Немає невідомих слів для додавання.",get_main_keyboard())
            return "OK",200

        elif action == "unknown_export":
            if os.path.exists(UNKNOWN_FILE):
                send_file(chat_id, UNKNOWN_FILE)
            else:
                send_message(chat_id,"⚠️ Файлу невідомих слів немає.",get_main_keyboard())
            return "OK",200

        elif action == "unknown_import":
            user_states[chat_id]={"action":"import_unknown_file"}
            send_message(chat_id,"📤 Надішліть файл .txt для імпорту невідомих слів.",get_main_keyboard())
            return "OK",200

        else:
            user_states[chat_id]={"action":action,"data":{}}
            send_message(chat_id,"Введіть дані для дії.",get_main_keyboard())
            return "OK",200

    # --- Обробка станів ---
    if state:
        action = state["action"]

        # --- Додати / редагувати словник (багаторядково) ---
        if action in ["add","edit"]:
            pairs = parse_multiline_input(text)
            reply_lines = []
            for k,v in pairs:
                if action=="add":
                    custom_map[k]=v
                    remove_unknown(k)
                    reply_lines.append(f"✅ Додано: *{k}*{SEP}`{v}`")
                else:
                    if k in custom_map:
                        custom_map[k]=v
                        remove_unknown(k)
                        reply_lines.append(f"✏️ Змінено: *{k}*{SEP}`{v}`")
                    else:
                        reply_lines.append(f"⚠️ Слова *{k}* немає в словнику")
            save_dict()
            user_states.pop(chat_id)
            send_message(chat_id,"\n".join(reply_lines),get_main_keyboard())
            return "OK",200

        # --- Транслітерація ---
        elif action=="translit":
            lines = text.splitlines()
            result_lines = [translit_text_line(l) for l in lines]
            user_states.pop(chat_id)
            send_message(chat_id,"\n".join(result_lines),get_main_keyboard())
            return "OK",200

        # --- Імпорт невідомих ---
        elif action=="import_unknown_file" and "document" in message:
            file_id = message["document"]["file_id"]
            file_info = requests.get(f"https://api.telegram.org/bot{TOKEN}/getFile?file_id={file_id}").json()
            file_path = file_info["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
            r = requests.get(file_url)
            content = r.content.decode("utf-8")
            for line in content.splitlines():
                if line.strip():
                    save_unknown(line)
            user_states.pop(chat_id)
            send_message(chat_id,"✅ Імпортовано невідомі слова.",get_main_keyboard())
            return "OK",200

        # --- Додати вручну невідомі ---
        elif action=="import_unknown_manual":
            pairs = parse_multiline_input(text)
            reply_lines=[]
            for k,v in pairs:
                custom_map[k]=v
                remove_unknown(k)
                reply_lines.append(f"✅ Додано: *{k}*{SEP}`{v}`")
            save_dict()
            user_states.pop(chat_id)
            send_message(chat_id,"\n".join(reply_lines),get_main_keyboard())
            return "OK",200

    # --- Автоматична транслітерація ---
    if text:
        result = translit_text_line(text)
        send_message(chat_id,result,get_main_keyboard())
    return "OK",200

# === Старт ===
@app.route("/",methods=["GET"])
def index():
    return "✅ Transliteration bot is running!"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",10000)))
