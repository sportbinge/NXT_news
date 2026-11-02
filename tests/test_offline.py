"""Offline tests - no internet or Telegram needed.  Run:  python tests/test_offline.py"""
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["BOT_TOKEN"] = "TEST"
os.environ["ADMIN_CHAT_ID"] = "111"
os.environ["CHANNEL_ID"] = "@nxt_test"
os.environ["PANDASCORE_TOKEN"] = "x"

from datetime import datetime, timezone
from email.utils import format_datetime

import news, live, formatting as fmt
import telegram_api as tg

NOW = time.time()
RFC = lambda ago_min: format_datetime(datetime.fromtimestamp(NOW - ago_min * 60, timezone.utc))

GNEWS = f"""<?xml version="1.0"?><rss><channel>
<item><title>Team Heretics win VALORANT Champions 2026 after reverse sweep - Dot Esports</title>
<link>https://news.google.com/a1</link><pubDate>{RFC(20)}</pubDate>
<description>&lt;a&gt;junk&lt;/a&gt;</description><source url="https://dotesports.com">Dot Esports</source></item>
<item><title>Top 10 VALORANT skins tier list - Sportskeeda</title><link>https://x/2</link><pubDate>{RFC(10)}</pubDate></item>
<item><title>Old CS2 story from last week - HLTV</title><link>https://x/3</link><pubDate>{RFC(60*24*5)}</pubDate></item>
<item><title>Arsenal beat Chelsea 2-0 - BBC</title><link>https://x/4</link><pubDate>{RFC(5)}</pubDate></item>
<item><title>S8UL signs BGMI roster ahead of BGIS 2026 - AFK Gaming</title><link>https://x/5</link><pubDate>{RFC(30)}</pubDate></item>
</channel></rss>""".encode()

SITE = f"""<?xml version="1.0"?><rss xmlns:media="http://search.yahoo.com/mrss/"><channel>
<item><title>Heretics win Valorant Champions 2026 with reverse sweep in grand final</title>
<link>https://esportsinsider.com/h</link><pubDate>{RFC(15)}</pubDate>
<description>&lt;p&gt;The Spanish side completed a stunning comeback in the grand final.&lt;/p&gt;</description>
<media:content url="https://img.example/h.jpg"/></item>
<item><title>Tekken 8 Season 3 patch notes</title><link>https://x/6</link><pubDate>{RFC(15)}</pubDate></item>
<item><title>Arslan Ash wins EVO Japan Tekken 8 grand final</title><link>https://x/7</link><pubDate>{RFC(40)}</pubDate></item>
</channel></rss>""".encode()

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>MOUZ qualify for CS2 Major playoffs</title><link href="https://hltv.org/1"/>
<updated>2026-11-02T03:00:00Z</updated></entry></feed>"""

fails = 0
def check(cond, label):
    global fails
    print(("PASS " if cond else "FAIL ") + label)
    fails += 0 if cond else 1


# ---- parsing
g = news.parse_feed(GNEWS, "GNews Valorant")
check(g[0]["title"] == "Team Heretics win VALORANT Champions 2026 after reverse sweep", "gnews title suffix stripped")
check(g[0]["source"] == "Dot Esports", "gnews source read")
s = news.parse_feed(SITE, "Esports Insider")
check(s[0]["image"] == "https://img.example/h.jpg", "media image read")
check("stunning comeback" in s[0]["summary"] and "<p>" not in s[0]["summary"], "summary cleaned")
a = news.parse_feed(ATOM, "HLTV")
check(a and a[0]["link"] == "https://hltv.org/1", "atom feed parsed")

# ---- classify
check(news.classify("Top 10 VALORANT skins tier list")[0] is None, "blocked junk dropped")
check(news.classify("Arsenal beat Chelsea 2-0")[0] is None, "non-esports dropped")
check(news.classify("Arslan Ash wins EVO Japan Tekken 8 grand final")[0] == "tekken", "tekken detected")
check(news.classify("S8UL signs BGMI roster ahead of BGIS 2026")[1]["india"], "india boost")
check(news.classify("MOUZ qualify for CS2 Major playoffs")[0] == "cs2", "cs2 detected")
check(news.classify("Mortal Kombat 1 Pro Kompetition finals set")[0] == "mk", "mk detected")
check(news.classify("Street Fighter 6 Capcom Cup prize pool revealed")[0] == "sf6", "sf6 detected")

# ---- process + cluster + score
state = {"seen": {}, "stories": {}, "muted_games": [], "matches": {}}
changed = news.process(g + s + a, state, NOW)
st = state["stories"]
titles = [x["title"] for x in st.values()]
check(not any("skins" in t for t in titles), "skins not stored")
check(not any("Old CS2" in t for t in titles), "old story ignored")
check(not any("Arsenal" in t for t in titles), "football ignored")
val = [x for x in st.values() if x["game"] == "valorant"]
check(len(val) == 1 and len(val[0]["sources"]) == 2, f"same Valorant story merged from 2 sites ({[v['sources'] for v in val]})")
check(val[0]["priority"] == 1, f"Champions win = P1 (score {val[0]['score']})")
check(val[0]["image"] == "https://img.example/h.jpg", "image picked up on merge")
bg = [x for x in st.values() if x["game"] == "bgmi"][0]
check(bg["priority"] <= 2, f"S8UL BGMI story P{bg['priority']} (score {bg['score']})")
check(len(news.process(g + s, state, NOW + 60)) == 0, "re-fetch adds nothing (no duplicates)")
ready = news.ready_to_send(state, NOW)
check(all(x["priority"] == 1 for x in ready), "only P1 skips the hold")
ready_later = news.ready_to_send(state, NOW + 10 * 60)
check(len(ready_later) == len(st), "everything ready after hold time")
news.process([], state, NOW)

# ---- live
running = [{"id": 1, "status": "running", "videogame": {"slug": "valorant"},
            "tournament": {"tier": "s", "name": "Playoffs"}, "league": {"name": "VCT"},
            "serie": {"full_name": "Champions 2026"}, "number_of_games": 5,
            "opponents": [{"opponent": {"id": 10, "name": "Sentinels"}}, {"opponent": {"id": 11, "name": "Fnatic"}}],
            "results": [{"team_id": 10, "score": 1}, {"team_id": 11, "score": 0}],
            "streams_list": [{"main": True, "raw_url": "https://twitch.tv/valorant", "language": "en"}]},
           {"id": 2, "status": "running", "videogame": {"slug": "valorant"}, "tournament": {"tier": "c"},
            "opponents": []}]
ls = {"stories": {}, "matches": {}, "muted_games": []}
alerts = live.apply(running, [], ls, NOW)
check(len(alerts) == 1 and "Sentinels vs Fnatic" in alerts[0]["title"], "live alert for S-tier only")
check(len(live.apply(running, [], ls, NOW)) == 0, "no repeat live alert")
fin = dict(running[0], status="finished", winner={"name": "Sentinels"},
           results=[{"team_id": 10, "score": 3}, {"team_id": 11, "score": 1}], end_at="2026-11-02T03:00:00Z")
res = live.apply([], [fin], ls, NOW)
check(len(res) == 1 and res[0]["title"] == "🏁 RESULT: Sentinels beat Fnatic 3–1", f"result alert ({res and res[0]['title']})")
check(len(live.apply([], [fin], ls, NOW)) == 0, "no repeat result")

# ---- formatting
post = fmt.channel_post(val[0])
check("🚨 <b>BREAKING</b>" in post and "#VALORANT" in post and "NXT" in post, "channel post format")
check(len(post) < 1024, "fits photo caption")
card = fmt.review_card(val[0])
check("CONFIRMED by 2 sources" in card, "review card shows confirmation")
print("\n--- sample channel post ---\n" + post + "\n--- live post ---\n" + fmt.channel_post(alerts[0]))

# ---- full bot flow with a fake Telegram
sent = []
def fake_call(method, _timeout=40, **p):
    sent.append((method, p))
    if method == "getChat":
        return {"title": "NXT Esports"}
    return {"message_id": len(sent)}
tg.call = fake_call
import bot
bot.state.data["stories"] = {k: dict(v) for k, v in st.items()}
for v in bot.state.data["stories"].values():
    v["first_seen"] = time.time() - 20 * 60
bot.state.data["mode"] = "review"
bot.deliver_ready()
reviews = [p for m, p in sent if p.get("chat_id") == "111" and p.get("reply_markup")]
check(len(reviews) >= 3, f"review cards sent to admin ({len(reviews)})")
sid = val[0]["id"]
bot.on_button({"id": "q", "data": f"post:{sid}", "message": {"chat": {"id": 111}, "message_id": 5}})
chan = [p for m, p in sent if p.get("chat_id") == "@nxt_test"]
check(len(chan) == 1 and chan[0].get("photo") == "https://img.example/h.jpg", "Post button posts photo to channel")
bot.on_button({"id": "q", "data": f"post:{sid}", "message": {"chat": {"id": 111}, "message_id": 5}})
check(len([p for m, p in sent if p.get("chat_id") == "@nxt_test"]) == 1, "double tap doesn't double post")
other = [x for x in bot.state.data["stories"] if x != sid][0]
bot.on_button({"id": "q", "data": f"edit:{other}", "message": {"chat": {"id": 111}, "message_id": 6}})
bot.on_text(111, "My own headline 🔥")
check(bot.state["stories"][other]["custom_text"] == "My own headline 🔥", "edit flow stores text")
bot.on_button({"id": "q", "data": "post:" + other, "message": {"chat": {"id": 111}, "message_id": 7}})
check("My own headline" in [p for m, p in sent if p.get("chat_id") == "@nxt_test"][-1]["text"], "edited text posted")
bot.on_button({"id": "q", "data": "noop:", "message": {"chat": {"id": 111}, "message_id": 7}})
# non-admin can't press buttons / admin commands
n = len(sent)
bot.on_button({"id": "q", "data": f"post:{sid}", "message": {"chat": {"id": 999}, "message_id": 1}})
bot.cmd(999, "/auto", 999)
check(bot.state["mode"] == "review", "stranger can't change mode")
for c in ["/start", "/help", "/news", "/status", "/games", "/sources", "/test", "/mute fortnite",
          "/unmute fortnite", "/say Hello NXT", "/pause", "/resume", "/auto", "/cancel", "/foo"]:
    try:
        bot.cmd(111, c, 111)
    except Exception as e:
        check(False, f"command {c} crashed: {e}")
check(bot.state["mode"] == "auto", "/auto switches mode")
# auto mode: new P1 goes straight to channel
before = len([p for m, p in sent if p.get("chat_id") == "@nxt_test"])
bot.state["stories"]["auto1"] = dict(val[0], id="auto1", status="new", first_seen=time.time())
bot.deliver_ready()
after = len([p for m, p in sent if p.get("chat_id") == "@nxt_test"])
check(after == before + 1, "auto mode posts P1 to channel")
bot.state.save()
check(os.path.exists(os.path.join(os.environ["DATA_DIR"], "state.json")), "state saved to disk")

print("\nALL PASSED" if not fails else f"\n{fails} FAILED")
sys.exit(1 if fails else 0)
