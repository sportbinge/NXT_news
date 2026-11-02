# NXT Esports News Bot (Telegram)

Watches esports news from 13 sources every 3 minutes, plus live matches every 90 seconds.
It works out which game each story is about, ranks it, merges duplicates from different sites,
and sends it to your Telegram channel.

**Priority games (tier 1):** VALORANT, CS2, BGMI, TEKKEN 8, Street Fighter 6, Mortal Kombat
**Tier 2:** LoL, Dota 2, EA FC, Free Fire, PUBG Mobile, Rainbow Six
**Tier 3:** Rocket League, Apex, Fortnite, CoD, MLBB, Overwatch

Stories get extra points for big events (Champions, Majors, EVO, EWC, BGIS…), real news words
(wins, signs, banned…), Indian teams/players, and being reported by 2+ sites (✅ CONFIRMED).
Result: 🔴 P1 / 🟠 P2 / 🟡 P3 / ⚪ P4.

---

## Setup (about 20 minutes, all free)

### 1. Create the bot (Telegram)
1. Open **@BotFather** → `/newbot` → name it e.g. *NXT Esports News* → username e.g. `nxt_esports_news_bot`.
2. Copy the **token** it gives you. Keep it private: it goes only into Railway, never into chats.

### 2. Create your channel (Telegram)
1. New Channel → e.g. *NXT Esports* → Public → link e.g. `t.me/nxt_esports`.
2. Channel → Administrators → **Add Admin** → search your bot → turn on **Post Messages** and **Delete Messages**.

### 3. Put the code on GitHub
1. github.com → **New repository** → name `nxt-esports-bot` → **Private** → Create.
2. Click **uploading an existing file** → **drag in all the files and the `tests` folder from the unzipped folder** (drag them; the button can't pick folders) → **Commit changes**.
   The files must sit on the repo's **front page**, not inside another folder.

### 4. Run it on Railway
1. railway.com → **New Project** → **Deploy from GitHub repo** → pick `nxt-esports-bot`.
2. Click the service → **Variables** → add:

| Name | Value |
|---|---|
| `BOT_TOKEN` | token from BotFather |
| `CHANNEL_ID` | `@nxt_esports` (your channel's @link) |
| `DATA_DIR` | `/data` |
| `ADMIN_CHAT_ID` | leave empty for now (step 5) |

3. Right-click the service → **Attach Volume** → mount path `/data`. This keeps the bot's memory so a restart doesn't re-send old news.
4. Click **Deploy**.

### 5. Make yourself the admin
1. Open your bot in Telegram → **Start**. It replies with **your chat id**.
2. Railway → Variables → `ADMIN_CHAT_ID` = that number → Deploy.
3. You'll get **"✅ NXT Esports bot started"**. Send `/test` to see a sample card.

### 6. (Optional, recommended) Live match + result alerts
1. Sign up free at **pandascore.co** (no card needed) → copy your API token from the dashboard.
2. Railway → Variables → `PANDASCORE_TOKEN` = token → Deploy.
   You now get **🔴 LIVE NOW** and **🏁 RESULT** alerts for top-tier VALORANT, CS2, LoL, Dota 2, R6, PUBG and more,
   plus `/live` and `/today`. (Fighting games and BGMI aren't in PandaScore, so they come from news only.)

---

## How it behaves

- **First start:** it quietly remembers the news that already exists and posts only what's new after that.
- **`/review` mode (default):** every P1–P3 story comes to you with **✅ Post · ✏️ Edit · ❌ Skip**. P4 stays in `/news` only.
- **`/auto` mode:** P1 and P2 go **straight to the channel**, and you get a silent note with a **🗑 Delete** button. P3 still comes to you.
- A story waits 6 minutes so other sites can confirm it. P1 stories and live alerts skip the wait.
- At most 8 auto-posts per hour. Extra stories come to you instead.

## Commands
Everyone: `/news` `/live` `/today` `/id`
Admin: `/status` `/review` `/auto` `/pause` `/resume` `/games` `/mute <game>` `/unmute <game>` `/say <text>` `/sources` `/test` `/cancel`

## Changing things
Everything is in **`config.py`**: game tiers, keywords, big-event names, Indian teams, blocked words and the feed list.
Edit it on GitHub (pencil icon) → Commit. Railway redeploys by itself.
Timing settings can also be Railway Variables: `NEWS_EVERY_SECONDS`, `HOLD_MINUTES`, `MAX_POSTS_PER_HOUR`,
`AUTO_MIN_PRIORITY` (1 = auto-post only P1), `MODE`, `SIGNATURE`, `LIVE_TIERS` (default `s,a`).

## Problems
- **No messages at all:** Railway → Deployments → View logs. `BOT_TOKEN is missing` means the variable name is wrong.
- **"Couldn't post to channel":** the bot isn't an admin of the channel, or `CHANNEL_ID` is wrong.
- **A source shows ❌ in `/sources`:** that site blocks bots. The others (especially the Google News ones) cover it.
- **Test locally:** `python tests/test_offline.py` (no internet needed).
