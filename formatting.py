"""How posts look in Telegram (HTML)."""
import html
import time

import config

BADGE = {1: "🔴 P1 BIG", 2: "🟠 P2 HIGH", 3: "🟡 P3", 4: "⚪ P4"}


def esc(s):
    return html.escape(s or "", quote=False)


def game_label(gid):
    g = config.GAMES.get(gid)
    return f"{g['emoji']} {g['name'].upper()}" if g else "🎮 ESPORTS"


def hashtags(s):
    g = config.GAMES.get(s["game"])
    tags = ["#Esports"]
    if g:
        tags.insert(0, "#" + "".join(ch for ch in g["name"] if ch.isalnum()))
    if s.get("india"):
        tags.append("#IndianEsports")
    return " ".join(tags)


def channel_post(s) -> str:
    """The text your audience sees."""
    if s.get("custom_text"):
        body = esc(s["custom_text"])
        return f"{body}\n\n{esc(config.SIGNATURE)}"
    lines = [f"<b>{game_label(s['game'])}</b>"]
    if s.get("priority") == 1 and s.get("kind") is None:
        lines[0] = "🚨 <b>BREAKING</b> · " + lines[0]
    lines.append("")
    lines.append(f"<b>{esc(s['title'])}</b>")
    if s.get("summary"):
        summ = s["summary"]
        if len(summ) > 280:
            summ = summ[:277].rsplit(" ", 1)[0] + "…"
        lines += ["", esc(summ)]
    lines.append("")
    if s.get("kind") == "live" and s.get("link"):
        lines.append(f'📺 <a href="{esc(s["link"])}">Watch live</a>')
    elif s.get("link"):
        src = s["sources"][0] if s.get("sources") else "Source"
        lines.append(f'🔗 <a href="{esc(s["link"])}">Read more on {esc(src)}</a>')
    lines += ["", hashtags(s), esc(config.SIGNATURE)]
    return "\n".join(lines)


def review_card(s) -> str:
    """What you see before approving."""
    srcs = s.get("sources", [])
    conf = "✅ CONFIRMED by %d sources" % len(srcs) if len(srcs) >= 2 else "📰 1 source"
    age = int((time.time() - s["first_seen"]) / 60)
    head = f"{BADGE.get(s['priority'], '')} · score {s['score']} · {conf} · seen {age}m ago"
    extra = ""
    if len(srcs) > 1:
        extra = "\n<i>Also on: " + esc(", ".join(srcs[1:6])) + "</i>"
    return f"<code>{esc(head)}</code>{extra}\n\n" + channel_post(s)


def review_buttons(sid):
    return [[{"text": "✅ Post", "callback_data": f"post:{sid}"},
             {"text": "✏️ Edit", "callback_data": f"edit:{sid}"},
             {"text": "❌ Skip", "callback_data": f"skip:{sid}"}]]


def news_list(stories, limit=10):
    if not stories:
        return "No esports stories tracked in the last few hours yet."
    mark = {"posted": "📤", "skipped": "❌", "review": "👀", "new": "⏳", "quiet": "💤",
            "seed": "•", "expired": "⌛"}
    out = ["<b>Top esports stories right now</b>\n"]
    for s in stories[:limit]:
        g = config.GAMES.get(s["game"])
        emoji = g["emoji"] if g else "🎮"
        n = len(s.get("sources", []))
        title = esc(s["title"][:110])
        link = s.get("link")
        t = f'<a href="{esc(link)}">{title}</a>' if link else title
        out.append(f"{mark.get(s['status'], '')} {BADGE.get(s['priority'], '')} {emoji} {t}"
                   + (f" <i>({n} sources)</i>" if n > 1 else ""))
    return "\n".join(out)


HELP = """<b>NXT Esports News Bot</b>

<b>For everyone</b>
/news – top esports stories right now
/live – matches being played now
/today – big matches in the next 24 h (IST)
/id – show your chat id

<b>Admin only</b>
/status – mode, channel, feeds, stats
/review – every story comes to you first (Post / Edit / Skip)
/auto – P1/P2 stories go straight to the channel
/pause · /resume – stop / restart sending
/games – game priority list
/mute valorant · /unmute valorant – turn a game off/on
/say your text – post your own message to the channel
/sources – which news sites are working
/test – send a sample card to yourself
/cancel – stop editing
"""
