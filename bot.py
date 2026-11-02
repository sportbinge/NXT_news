"""NXT Esports News Bot - entry point.  Run:  python bot.py"""
import html
import sys
import threading
import time
import traceback

import config
import formatting as fmt
import live
import news
import telegram_api as tg
from storage import State

state = State()
LOG = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def is_admin(chat_id) -> bool:
    return bool(config.ADMIN_CHAT_ID) and str(chat_id) == str(config.ADMIN_CHAT_ID)


def to_admin(text, **kw):
    if config.ADMIN_CHAT_ID:
        try:
            return tg.send(config.ADMIN_CHAT_ID, text, **kw)
        except tg.TelegramError as e:
            LOG("admin send failed:", e)


# ------------------------------------------------------------------ posting
def post_to_channel(s) -> bool:
    if not config.CHANNEL_ID:
        to_admin("⚠️ CHANNEL_ID is not set in Railway Variables, so I can't post to the channel.")
        return False
    try:
        msg = tg.send(config.CHANNEL_ID, fmt.channel_post(s), image=s.get("image"),
                      preview=not s.get("image"))
    except tg.TelegramError as e:
        to_admin(f"⚠️ Couldn't post to channel: {html.escape(str(e))}\n"
                 "Check the bot is an <b>admin</b> of the channel with 'Post messages' on.")
        return False
    with state.lock:
        s["status"] = "posted"
        s["channel_msg"] = msg["message_id"]
        state["posted_times"].append(time.time())
        state["stats"]["posted"] += 1
    return True


def under_rate_limit() -> bool:
    hour_ago = time.time() - 3600
    return len([t for t in state["posted_times"] if t > hour_ago]) < config.MAX_POSTS_PER_HOUR


def send_for_review(s):
    msg = to_admin(fmt.review_card(s), buttons=fmt.review_buttons(s["id"]),
                   image=s.get("image"), preview=False, silent=s["priority"] >= 3)
    if msg:
        s["status"] = "review"
        s["review_msg"] = msg["message_id"]


def deliver(s):
    """Decide what happens to one ready story."""
    if s["priority"] >= 4 and not s.get("instant"):
        s["status"] = "quiet"           # kept for /news, not pushed to anyone
        return
    auto = state["mode"] == "auto" and s["priority"] <= config.AUTO_MIN_PRIORITY
    if auto and under_rate_limit():
        if post_to_channel(s):
            state["stats"]["auto"] += 1
            to_admin(f"📤 Auto-posted: {html.escape(s['title'][:120])}", silent=True,
                     buttons=[[{"text": "🗑 Delete from channel",
                                "callback_data": f"del:{s['id']}"}]])
        return
    if config.ADMIN_CHAT_ID:
        send_for_review(s)
    elif state["mode"] == "auto":
        post_to_channel(s)


def deliver_ready():
    if state["paused"]:
        return
    now = time.time()
    for s in news.ready_to_send(state, now):
        if now - s["first_seen"] > 2 * 3600:   # too old (e.g. bot was paused)
            s["status"] = "expired"
            continue
        try:
            deliver(s)
        except Exception as e:
            LOG("deliver error:", e)
        time.sleep(1.2)   # stay well under Telegram limits


# ------------------------------------------------------------------ background loop
def news_round(seeding=False):
    items, status = news.fetch_all()
    with state.lock:
        state["feed_status"].update(status)
        changed = news.process(items, state)
        if seeding:
            for s in state["stories"].values():
                if s["status"] == "new":
                    s["status"] = "seed"
    bad = [n for n, st in status.items() if not st["ok"]]
    LOG(f"news: {len(items)} items, {len(changed)} new/updated stories, {len(bad)} feeds failing")


def live_round(seeding=False):
    try:
        with state.lock:
            alerts = live.check(state, seeding=seeding)
        if alerts:
            state["stats"]["live_alerts"] += len(alerts)
            LOG(f"live: {len(alerts)} alerts")
    except Exception as e:
        LOG("live error:", e)


def worker():
    if not state["seeded"]:
        LOG("first run: remembering current news without posting it")
        news_round(seeding=True)
        live_round(seeding=True)
        state["seeded"] = True
        state.save()
    to_admin("✅ <b>NXT Esports bot started</b>\n"
             f"Mode: <b>{state['mode']}</b> · watching {len(config.FEEDS)} feeds"
             f" · live alerts {'ON' if config.PANDASCORE_TOKEN else 'OFF'}\nSend /help for commands.")
    next_news = next_live = 0
    while True:
        try:
            now = time.time()
            if now >= next_news:
                news_round()
                next_news = now + config.NEWS_EVERY_SECONDS
            if config.PANDASCORE_TOKEN and now >= next_live:
                live_round()
                next_live = now + config.LIVE_EVERY_SECONDS
            deliver_ready()
            state.save()
        except Exception:
            LOG("worker error:\n" + traceback.format_exc())
        time.sleep(15)


# ------------------------------------------------------------------ commands
def cmd(chat_id, text, user_id):
    parts = text.strip().split(maxsplit=1)
    c = parts[0].split("@")[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    admin = is_admin(chat_id)

    if c in ("/start", "/help"):
        msg = fmt.HELP
        if not config.ADMIN_CHAT_ID:
            msg += (f"\n⚙️ <b>Setup:</b> your chat id is <code>{chat_id}</code>. "
                    "Put it in Railway → Variables as <code>ADMIN_CHAT_ID</code>.")
        return tg.send(chat_id, msg)
    if c == "/id":
        return tg.send(chat_id, f"Your chat id: <code>{chat_id}</code>")
    if c == "/news":
        with state.lock:
            cutoff = time.time() - config.MAX_AGE_HOURS * 3600
            st = [s for s in state["stories"].values()
                  if s["first_seen"] > cutoff and s["status"] != "skipped"]
        st.sort(key=lambda s: (s["priority"], -s["score"]))
        return tg.send(chat_id, fmt.news_list(st), preview=False)
    if c in ("/live", "/today"):
        try:
            lines = live.running_now(state) if c == "/live" else live.upcoming_today()
        except Exception as e:
            return tg.send(chat_id, f"Couldn't reach the match service right now ({html.escape(str(e)[:80])}).")
        if lines is None:
            return tg.send(chat_id, "Live match data is off. Admin: add <code>PANDASCORE_TOKEN</code> in Railway.")
        head = "🔴 <b>Live now</b>" if c == "/live" else "📅 <b>Big matches – next 24 h (IST)</b>"
        return tg.send(chat_id, head + "\n\n" + ("\n".join(lines) if lines else "Nothing right now."),
                       preview=False)

    if not admin:
        return tg.send(chat_id, "That command is for the NXT admin only. Try /news, /live or /today.")

    if c == "/status":
        fs = state["feed_status"]
        ok = sum(1 for v in fs.values() if v["ok"])
        stt = state["stats"]
        chan = config.CHANNEL_ID or "NOT SET"
        try:
            if config.CHANNEL_ID:
                chan = tg.call("getChat", chat_id=config.CHANNEL_ID).get("title", chan)
        except tg.TelegramError as e:
            chan += f" ⚠️ ({e})"
        return tg.send(chat_id, (
            f"<b>Status</b>\nMode: <b>{state['mode']}</b>{' · ⏸ PAUSED' if state['paused'] else ''}\n"
            f"Channel: {html.escape(str(chan))}\nFeeds working: {ok}/{len(fs)}\n"
            f"Live alerts: {'ON' if config.PANDASCORE_TOKEN else 'OFF (no PANDASCORE_TOKEN)'}\n"
            f"Muted: {', '.join(state['muted_games']) or 'none'}\n"
            f"Tracked stories: {len(state['stories'])}\n"
            f"Posted: {stt['posted']} (auto {stt['auto']}) · skipped {stt['skipped']} · live alerts {stt['live_alerts']}\n"
            f"Posts in last hour: {len(state['posted_times'])}/{config.MAX_POSTS_PER_HOUR}"))
    if c in ("/auto", "/review"):
        state["mode"] = c[1:]
        state.save()
        return tg.send(chat_id, "Mode: <b>auto</b> – P1" + ("" if config.AUTO_MIN_PRIORITY == 1 else
                       f"–P{config.AUTO_MIN_PRIORITY}") + " stories post straight to the channel, the rest come to you."
                       if c == "/auto" else "Mode: <b>review</b> – every story comes to you first.")
    if c == "/pause":
        state["paused"] = True; state.save()
        return tg.send(chat_id, "⏸ Paused. I'll keep tracking news but won't send anything. /resume to restart.")
    if c == "/resume":
        state["paused"] = False; state.save()
        return tg.send(chat_id, "▶️ Resumed.")
    if c == "/games":
        rows = sorted(config.GAMES.items(), key=lambda x: x[1]["tier"])
        lines = [f"{'🔇' if gid in state['muted_games'] else ''}{g['emoji']} <b>{g['name']}</b> – tier {g['tier']}"
                 f"{' · live' if g['pandascore'] else ''} (<code>{gid}</code>)" for gid, g in rows]
        return tg.send(chat_id, "<b>Game priorities</b> (tier 1 = highest)\n\n" + "\n".join(lines))
    if c in ("/mute", "/unmute"):
        gid = arg.lower()
        if gid not in config.GAMES:
            return tg.send(chat_id, "Use the code from /games, e.g. <code>/mute fortnite</code>")
        muted = set(state["muted_games"])
        (muted.add if c == "/mute" else muted.discard)(gid)
        state["muted_games"] = sorted(muted); state.save()
        return tg.send(chat_id, f"{'🔇 Muted' if c == '/mute' else '🔊 Unmuted'} {config.GAMES[gid]['name']}.")
    if c == "/say":
        if not arg:
            return tg.send(chat_id, "Write the message after /say, e.g. <code>/say Big VCT final tonight!</code>")
        s = {"id": f"say{int(time.time())}", "custom_text": arg, "status": "new", "sources": [],
             "game": "general", "priority": 1, "score": 0, "first_seen": time.time(), "title": arg[:60]}
        ok = post_to_channel(s)
        return tg.send(chat_id, "📤 Posted to the channel." if ok else "Not posted.")
    if c == "/sources":
        fs = state["feed_status"]
        lines = [f"{'✅' if v['ok'] else '❌'} {html.escape(n)} – {v['items']} items"
                 + (f"\n     <i>{html.escape(v['err'][:80])}</i>" if v["err"] else "")
                 for n, v in sorted(fs.items())]
        return tg.send(chat_id, "<b>News sources</b>\n" + ("\n".join(lines) or "Not checked yet."))
    if c == "/test":
        s = {"id": "test", "title": "Team Heretics win VALORANT Champions after reverse sweep",
             "summary": "Sample card only – this is what a big story looks like.", "link": "https://www.vlr.gg",
             "sources": ["VLR.gg", "Dot Esports"], "game": "valorant", "priority": 1, "score": 95,
             "first_seen": time.time(), "status": "test", "big_event": True}
        return tg.send(chat_id, fmt.review_card(s), preview=False)
    if c == "/cancel":
        state["pending_edit"] = None
        return tg.send(chat_id, "OK, cancelled.")
    return tg.send(chat_id, "Unknown command. Send /help.")


def on_text(chat_id, text):
    """Plain text from admin = new text for the story being edited."""
    sid = state["pending_edit"]
    if not is_admin(chat_id) or not sid:
        return tg.send(chat_id, "Send /help to see what I can do.")
    s = state["stories"].get(sid)
    state["pending_edit"] = None
    if not s:
        return tg.send(chat_id, "That story has expired.")
    s["custom_text"] = text
    state.save()
    tg.send(chat_id, "<b>Preview of your edited post:</b>\n\n" + fmt.channel_post(s),
            buttons=fmt.review_buttons(sid), preview=False)


def on_button(q):
    data = q.get("data", "")
    chat_id = q["message"]["chat"]["id"]
    msg_id = q["message"]["message_id"]
    if not is_admin(chat_id):
        return tg.answer(q["id"], "Admin only")
    action, _, sid = data.partition(":")
    if action == "noop":
        return tg.answer(q["id"])
    s = state["stories"].get(sid)
    if not s:
        tg.set_buttons(chat_id, msg_id, None)
        return tg.answer(q["id"], "This story has expired.")
    if action == "post":
        if s["status"] == "posted":
            return tg.answer(q["id"], "Already posted")
        ok = post_to_channel(s)
        tg.answer(q["id"], "Posted ✅" if ok else "Failed – see message")
        if ok:
            tg.set_buttons(chat_id, msg_id, [[{"text": "✅ Posted", "callback_data": "noop:"},
                                              {"text": "🗑 Delete", "callback_data": f"del:{sid}"}]])
    elif action == "skip":
        s["status"] = "skipped"
        state["stats"]["skipped"] += 1
        tg.answer(q["id"], "Skipped")
        tg.set_buttons(chat_id, msg_id, [[{"text": "❌ Skipped", "callback_data": "noop:"}]])
    elif action == "edit":
        state["pending_edit"] = sid
        tg.answer(q["id"])
        tg.send(chat_id, "✏️ Send me the full new text for this post as your next message.\n"
                         "(Signature is added automatically. /cancel to stop.)\n\n<b>Current:</b>\n"
                + html.escape(s.get("custom_text") or s["title"]))
    elif action == "del":
        mid = s.get("channel_msg")
        try:
            tg.call("deleteMessage", chat_id=config.CHANNEL_ID, message_id=mid)
            s["status"] = "skipped"
            tg.answer(q["id"], "Deleted from channel")
            tg.set_buttons(chat_id, msg_id, [[{"text": "🗑 Deleted", "callback_data": "noop:"}]])
        except tg.TelegramError as e:
            tg.answer(q["id"], f"Couldn't delete: {e}")
    else:
        tg.answer(q["id"])
    state.save()


def poll_updates():
    offset = None
    while True:
        try:
            updates = tg.call("getUpdates", _timeout=60, offset=offset, timeout=45,
                              allowed_updates=["message", "callback_query"])
        except Exception as e:
            if "Conflict" in str(e):
                LOG("CONFLICT: another program is running with this same BOT_TOKEN "
                    "(e.g. the Sports Binge bot, an old Railway service, or your laptop). "
                    "Each bot needs its own token from @BotFather.")
                time.sleep(30)
            else:
                LOG("getUpdates error:", e)
                time.sleep(5)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            try:
                if "callback_query" in u:
                    on_button(u["callback_query"])
                elif "message" in u and "text" in u["message"]:
                    m = u["message"]
                    if m["chat"]["type"] != "private":
                        continue
                    if m["text"].startswith("/"):
                        cmd(m["chat"]["id"], m["text"], m["from"]["id"])
                    else:
                        on_text(m["chat"]["id"], m["text"])
            except Exception:
                LOG("update error:\n" + traceback.format_exc())


def main():
    # Startup check - shows which settings Railway is giving the bot (values hidden)
    def shown(name, val):
        return f"{name}={'SET (' + str(len(val)) + ' chars)' if val else 'MISSING'}"
    print("SETTINGS:", shown("BOT_TOKEN", config.BOT_TOKEN), shown("CHANNEL_ID", config.CHANNEL_ID),
          shown("ADMIN_CHAT_ID", config.ADMIN_CHAT_ID), shown("PANDASCORE_TOKEN", config.PANDASCORE_TOKEN),
          f"DATA_DIR={config.DATA_DIR}", flush=True)
    import os
    similar = [k for k in os.environ if "TOKEN" in k.upper() and k != "BOT_TOKEN"
               and k != "PANDASCORE_TOKEN"]
    if similar:
        print("NOTE: found variables with similar names:", similar,
              "- the bot only reads one named exactly BOT_TOKEN", flush=True)
    if not config.BOT_TOKEN:
        print("STOP: BOT_TOKEN is missing. Railway -> click the bot service -> Variables -> "
              "add BOT_TOKEN -> click Deploy in the purple bar.", flush=True)
        time.sleep(300)   # wait instead of crash-looping so the logs stay readable
        sys.exit(1)
    if ":" not in config.BOT_TOKEN or " " in config.BOT_TOKEN:
        print("STOP: BOT_TOKEN doesn't look like a BotFather token (should be like 123456789:ABC...). "
              "Re-copy it from @BotFather -> /mybots -> your bot -> API Token.", flush=True)
        time.sleep(300)
        sys.exit(1)
    try:
        me = tg.call("getMe")
    except Exception as e:
        print(f"STOP: Telegram rejected the token ({e}). Re-copy it from @BotFather -> /mybots -> "
              "API Token. If you pressed 'Revoke', the old token no longer works.", flush=True)
        time.sleep(300)
        sys.exit(1)
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        open(os.path.join(config.DATA_DIR, ".write_test"), "w").close()
    except OSError as e:
        print(f"WARNING: can't write to DATA_DIR {config.DATA_DIR} ({e}). "
              "Check the Volume mount path is /data.", flush=True)
    LOG(f"running as @{me['username']} · mode={state['mode']} · data={config.DATA_DIR}")
    tg.call("deleteWebhook")
    threading.Thread(target=worker, daemon=True).start()
    poll_updates()


if __name__ == "__main__":
    main()
