@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def receive_update():
    update = request.get_json()
    if not update:
        return "No update", 400

    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()

    if not chat_id or not text:
        return "No text", 200

    reply = ""
    parts = text.split(maxsplit=2)

    if text.startswith("/start"):
        reply = (
            "👋 Привіт! Я бот для транслітерації 🇺🇦🇷🇺\n"
            "Надішли слово українською або російською — я зроблю його транслітерацію.\n\n"
            "📝 Команди для роботи зі словником:\n"
            "`/add слово translit` - додати слово\n"
            "`/edit слово translit` - змінити трансліт\n"
            "`/delete слово` - видалити слово\n"
            "`/list` - показати весь словник\n"
            "`/translit текст` - транслітерувати текст"
        )

    elif text.startswith("/add "):
        if len(parts) != 3:
            reply = "⚠️ Формат команди: `/add слово translit`"
        else:
            orig, trans = parts[1].lower(), parts[2].lower()
            custom_map[orig] = trans
            save_dict()
            reply = f"✅ Додано: *{orig}* → `{trans}`"

    elif text.startswith("/edit "):
        if len(parts) != 3:
            reply = "⚠️ Формат команди: `/edit слово translit`"
        else:
            orig, trans = parts[1].lower(), parts[2].lower()
            if orig in custom_map:
                custom_map[orig] = trans
                save_dict()
                reply = f"✏️ Змінено: *{orig}* → `{trans}`"
            else:
                reply = f"⚠️ Слова *{orig}* немає в словнику"

    elif text.startswith("/delete "):
        if len(parts) != 2:
            reply = "⚠️ Формат команди: `/delete слово`"
        else:
            orig = parts[1].lower()
            if orig in custom_map:
                del custom_map[orig]
                save_dict()
                reply = f"🗑️ Видалено слово *{orig}*"
            else:
                reply = f"⚠️ Слова *{orig}* немає в словнику"

    elif text.startswith("/list"):
        if custom_map:
            lines = [f"*{k}* → `{v}`" for k, v in custom_map.items()]
            reply = "📚 Словник:\n" + "\n".join(lines)
        else:
            reply = "📭 Словник порожній"

    elif text.startswith("/translit "):
        text_to_translit = text[len("/translit "):]
        words = text_to_translit.split()
        result_words = []
        for w in words:
            lw = w.lower()
            if lw in custom_map:
                result_words.append(custom_map[lw])
            else:
                result_words.append(transliterate(w))
        translit_text = "_".join(result_words)
        reply = f"🔤 {text_to_translit} → `{translit_text}`"

    else:
        # Якщо просто слово
        key = text.lower()
        if key in custom_map:
            translit = custom_map[key]
            source = "📘 З твого словника"
        else:
            translit = transliterate(text)
            source = "🤖 Автоматична транслітерація"
        search_url = f"https://t.me/s/{translit}"
        reply = (
            f"🔤 *{text}* → `{translit}`\n"
            f"{source}\n\n"
            f"🔗 [Пошук у Telegram]({search_url})"
        )

    requests.post(API_URL + "sendMessage", json={
        "chat_id": chat_id,
        "text": reply,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    })

    return "OK", 200

def save_dict():
    with open(CUSTOM_FILE, "w", encoding="utf-8") as f:
        json.dump(custom_map, f, ensure_ascii=False, indent=2)
