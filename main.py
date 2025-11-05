elif action=="import_unknown_manual" and "data" in state:
    lines = state["data"]["lines"]
    # Якщо користувач нічого не відправив — додати автоматично
    if not text.strip():
        pairs = [(w, transliterate(w)) for w in lines]
    else:
        pairs = parse_multiline_input(text)  # Якщо користувач надав свій варіант

    reply_lines=[]
    for k,v in pairs:
        custom_map[k.lower()] = v
        remove_unknown(k)
        reply_lines.append(f"✅ Додано: *{k}*{SEP}`{v}`")
    save_dict()
    user_states.pop(chat_id)
    send_message(chat_id,"\n".join(reply_lines),get_main_keyboard())
    return "OK",200
