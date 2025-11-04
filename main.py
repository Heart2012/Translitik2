import os
import json
import requests
from flask import Flask, request

# === Налаштування ===
TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN"
CUSTOM_DICT_FILE = "custom_dict.json"
UNKNOWN_FILE = "unknown_words.txt"

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
            ["⚠️ Невідомі слова","📥 Додати невідомі у словник","📤 Скинути всі невідомі"]
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
        if "=" in line:
            parts = line.split("=",1)
            pairs.append((parts[0].strip().lower(), parts[1].strip()))
    return pairs

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
        "📥 Додати невідомі у словник":"import_unknown"
    }

    if text in buttons:
        action = buttons[text]

        # --- Дії ---
        if action == "list":
            reply = "📚 *Словник:*\n" + "\n".join(f"*{k}*=`{v}`" for k,v in custom_map.items()) if custom_map else "📭 Словник порожній."
            send_message(chat_id, reply, get_main_keyboard())
            return "OK",200

        elif action == "export":
            if custom_map:
                filename = "custom_export.txt"
                with open(filename,"w",encoding="utf-8") as f:
                    for k,v in custom_map.items():
                        f.write(f"{k}={v}\n")
                send_file(chat_id, filename)
            else:
                send_message(chat_id,"📭 Словник порожній.",get_main_keyboard())
            return "OK",200

        elif action == "unknown":
            if os.path.exists(UNKNOWN_FILE):
                with open(UNKNOWN_FILE,"r",encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                reply = "⚠️ *Невідомі слова/фрази:*\n" + "\n".join(f"[{w}]" for w in lines) if lines else "✅ Невідомих слів немає."
            else:
                reply = "✅ Невідомих слів немає."
            send_message(chat_id,reply,get_main_keyboard())
            return "OK",200

        elif action == "unknown_clear":
            clear_unknown()
            send_message(chat_id,"✅ Список невідомих слів очищено.",get_main_keyboard())
            return "OK",200

        elif action == "import_unknown":
            if not os.path.exists(UNKNOWN_FILE):
                send_message(chat_id,"⚠️ Файлу невідомих слів немає.",get_main_keyboard())
            else:
                # показати невідомі та запропонувати вставити свої трансліт рядками word=translit
                with open(UNKNOWN_FILE,"r",encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                if lines:
                    example = "\n".join([f"{w}={transliterate(w)}" for w in lines])
                    send_message(chat_id,"Вставте ручну транслітерацію або підтвердіть авто, відправивши:\n"+example,get_main_keyboard())
                    user_states[chat_id]={"action":"import_unknown_manual","data":{"lines":lines}}
            return "OK",200

        # --- Стани для введення ---
        user_states[chat_id] = {"action": action}
        prompts = {
            "add":"Введіть кілька рядків `слово=translit` або фраз, кожен з нового рядка:",
            "edit":"Введіть кілька рядків `слово=новий_translit`:",
            "delete":"Введіть по одному слову/фразі на рядок для видалення:",
            "translit":"Введіть текст (можна кілька рядків) для транслітерації:",
            "import":"📤 Надішліть .txt файл або вставте список `слово=translit` рядками."
        }
        if action not in ["import_unknown","unknown","unknown_clear","export","list"]:
            send_message(chat_id,prompts.get(action,"Введіть дані:"),get_main_keyboard())
        return "OK",200

    # === Обробка станів ===
    if state and text:
        action = state["action"]
        reply=""
        try:
            if action in ["add","edit"]:
                pairs=parse_multiline_input(text)
                count=0
                for w,t in pairs:
                    if action=="add" or (action=="edit" and w in custom_map):
                        custom_map[w]=t
                        remove_unknown(w)
                        count+=1
                save_dict()
                reply=f"✅ Оброблено {count} слів/фраз."

            elif action=="delete":
                words=[w.strip().lower() for w in text.splitlines() if w.strip()]
                count=0
                for w in words:
                    if w in custom_map:
                        del custom_map[w]
                        remove_unknown(w)
                        count+=1
                save_dict()
                reply=f"🗑️ Видалено {count} слів/фраз."

            elif action=="translit":
                lines=text.splitlines()
                result_lines=[]
                for line in lines:
                    lw=line.lower()
                    if lw in custom_map:
                        translit_line=custom_map[lw]
                        remove_unknown(lw)
                    else:
                        translit_line=f"[{transliterate(line)}]" # виділення невідомих
                        save_unknown(line)
                    result_lines.append(translit_line)
                reply="\n".join(result_lines)

            elif action=="import_unknown_manual":
                pairs=parse_multiline_input(text)
                for w,t in pairs:
                    custom_map[w]=t
                    remove_unknown(w)
                save_dict()
                reply=f"✅ Додано {len(pairs)} невідомих слів/фраз у словник."
                user_states.pop(chat_id,None)
        except Exception as e:
            reply=f"⚠️ Сталася помилка: {e}"

        user_states.pop(chat_id,None)
        send_message(chat_id,reply,get_main_keyboard())
        return "OK",200

    # === Автоматична транслітерація одиночного рядка ===
    lw=text.lower()
    if lw in custom_map:
        translit=custom_map[lw]
        remove_unknown(lw)
    else:
        translit=f"[{transliterate(text)}]"
        save_unknown(text)
    send_message(chat_id,translit,get_main_keyboard())
    return "OK",200

# === Стартова сторінка ===
@app.route("/", methods=["GET"])
def index():
    return "✅ Bot is running!"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",10000)))
