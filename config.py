"""
NXT Esports News Bot - settings.

Everything you might want to change lives in this file:
  * GAMES      - which games to track, their priority, and the words that identify them
  * BIG_EVENTS - tournament names that make a story more important
  * FEEDS      - where the news comes from
Secrets (bot token etc.) are NOT stored here. They go in Railway > Variables.
"""
import os

# ---------------------------------------------------------------- secrets / env
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip().strip("\"'").strip()
# Your own Telegram user id (the bot sends review cards + admin messages here)
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
# The public channel your audience follows, e.g. @nxt_esports or -1001234567890
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip().strip("\"'").strip()
# Optional - free key from pandascore.co, turns on live match / result alerts
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN", "").strip()
# Where the bot keeps its memory. On Railway attach a Volume at /data and set DATA_DIR=/data
DATA_DIR = os.getenv("DATA_DIR", "./data")

# ---------------------------------------------------------------- timing
NEWS_EVERY_SECONDS = int(os.getenv("NEWS_EVERY_SECONDS", "180"))   # check news every 3 min
LIVE_EVERY_SECONDS = int(os.getenv("LIVE_EVERY_SECONDS", "90"))    # check live matches every 90 s
MAX_AGE_HOURS = int(os.getenv("MAX_AGE_HOURS", "12"))              # ignore older stories
# Wait this long after first seeing a story before sending it (lets other sources
# catch up so the card can say CONFIRMED). P1 stories skip the wait.
HOLD_MINUTES = int(os.getenv("HOLD_MINUTES", "6"))
# Max channel posts per hour in auto mode (stops spam during huge events)
MAX_POSTS_PER_HOUR = int(os.getenv("MAX_POSTS_PER_HOUR", "8"))

# Starting mode. You can switch any time in Telegram with /auto or /review.
#   review = every story comes to YOU first with Post / Skip / Edit buttons
#   auto   = stories at or above AUTO_MIN_PRIORITY go straight to the channel
DEFAULT_MODE = os.getenv("MODE", "review").lower()
AUTO_MIN_PRIORITY = int(os.getenv("AUTO_MIN_PRIORITY", "2"))  # 1 = only P1, 2 = P1+P2 ...

# Brand line added under every channel post
SIGNATURE = os.getenv("SIGNATURE", "⚡ NXT Esports · @NXT_DELHI")

# ---------------------------------------------------------------- games
# tier 1 = top priority, 3 = covered but low priority.
# "words" are matched as whole words, case-insensitive.
# "pandascore" = the game's slug on PandaScore for live matches (None = no live data).
GAMES = {
    "valorant": {
        "name": "VALORANT", "emoji": "🎯", "tier": 1, "pandascore": "valorant",
        "words": ["valorant", "vct", "valorant champions", "valorant masters",
                  "game changers", "challengers league", "vct pacific", "vct emea",
                  "vct americas", "vct china"],
    },
    "cs2": {
        "name": "Counter-Strike 2", "emoji": "💣", "tier": 1, "pandascore": "cs-go",
        "words": ["cs2", "counter-strike", "counter strike", "csgo", "cs:go", "hltv",
                  "iem", "blast premier", "blast", "esl pro league", "pgl", "cs major",
                  "perfect world"],
    },
    "bgmi": {
        "name": "BGMI", "emoji": "🪂", "tier": 1, "pandascore": None,
        "words": ["bgmi", "battlegrounds mobile india", "bgis", "bmps", "bgms",
                  "bgmi masters"],
    },
    "tekken": {
        "name": "TEKKEN 8", "emoji": "👊", "tier": 1, "pandascore": None,
        "words": ["tekken", "tekken 8", "tekken world tour", "twt"],
    },
    "sf6": {
        "name": "Street Fighter 6", "emoji": "🥋", "tier": 1, "pandascore": None,
        "words": ["street fighter", "sf6", "capcom cup", "capcom pro tour", "cpt",
                  "street fighter league"],
    },
    "mk": {
        "name": "Mortal Kombat", "emoji": "🐉", "tier": 1, "pandascore": None,
        "words": ["mortal kombat", "mk1", "mortal kombat 1", "mk pro kompetition",
                  "pro kompetition"],
    },
    "lol": {
        "name": "League of Legends", "emoji": "🏆", "tier": 2, "pandascore": "league-of-legends",
        "words": ["league of legends", "lol worlds", "lck", "lec", "lpl", "lcs", "msi",
                  "faker", "t1", "worlds 2026"],
    },
    "dota2": {
        "name": "Dota 2", "emoji": "🛡️", "tier": 2, "pandascore": "dota-2",
        "words": ["dota 2", "dota", "the international", "riyadh masters", "dreamleague"],
    },
    "eafc": {
        "name": "EA FC", "emoji": "⚽", "tier": 2, "pandascore": None,
        "words": ["ea fc", "fc 26", "fc26", "fc pro", "ea sports fc", "fifae", "efootball"],
    },
    "freefire": {
        "name": "Free Fire", "emoji": "🔥", "tier": 2, "pandascore": None,
        "words": ["free fire", "free fire max", "ffws", "free fire world series"],
    },
    "pubgm": {
        "name": "PUBG Mobile", "emoji": "📱", "tier": 2, "pandascore": "pubg",
        "words": ["pubg mobile", "pmgc", "pmwc", "pubg"],
    },
    "r6": {
        "name": "Rainbow Six Siege", "emoji": "🪖", "tier": 2, "pandascore": "r6-siege",
        "words": ["rainbow six", "r6 siege", "siege x", "six invitational", "r6"],
    },
    "rl": {
        "name": "Rocket League", "emoji": "🚗", "tier": 3, "pandascore": "rl",
        "words": ["rocket league", "rlcs"],
    },
    "apex": {
        "name": "Apex Legends", "emoji": "🦾", "tier": 3, "pandascore": None,
        "words": ["apex legends", "algs"],
    },
    "fortnite": {
        "name": "Fortnite", "emoji": "🏗️", "tier": 3, "pandascore": None,
        "words": ["fortnite", "fncs"],
    },
    "cod": {
        "name": "Call of Duty", "emoji": "🔫", "tier": 3, "pandascore": "cod-mw",
        "words": ["call of duty league", "cdl", "call of duty", "warzone"],
    },
    "mlbb": {
        "name": "Mobile Legends", "emoji": "⚔️", "tier": 3, "pandascore": "mlbb",
        "words": ["mobile legends", "mlbb", "m7 world", "mpl"],
    },
    "ow": {
        "name": "Overwatch 2", "emoji": "🧡", "tier": 3, "pandascore": "ow",
        "words": ["overwatch", "owcs"],
    },
}

# Multi-game / general esports words (story counts as esports but no single game)
GENERAL_WORDS = ["esports", "e-sports", "esports world cup", "ewc", "olympic esports",
                 "evo", "evo japan", "evo 2026", "evo 2027", "combo breaker", "esports nations cup"]

# Tournament names that make a story "big". Matched as whole words.
BIG_EVENTS = [
    "champions", "masters", "major", "grand final", "grand finals", "world championship",
    "worlds", "the international", "esports world cup", "ewc", "evo", "capcom cup",
    "tekken world tour finals", "twt finals", "iem cologne", "iem katowice", "blast",
    "pgl major", "six invitational", "pmgc", "ffws", "bgis", "bmps", "olympic esports games",
    "asian games", "esports nations cup", "lan final", "playoffs", "final",
]

# Words that usually mean real news, not filler
BREAKING_WORDS = [
    "wins", "win", "won", "champion", "champions", "crowned", "lift", "lifts", "defeat",
    "defeats", "eliminated", "knocked out", "upset", "sweep", "signs", "signed", "joins",
    "transfer", "roster", "benched", "released", "leaves", "parts ways", "banned", "ban",
    "suspended", "cheating", "announced", "announces", "prize pool", "record",
    "viewership", "qualify", "qualified", "qualifies", "breaking", "official",
]

# Stories mentioning India get a boost - your audience is in Delhi
INDIA_WORDS = ["india", "indian", "delhi", "mumbai", "bengaluru", "hyderabad", "s8ul",
               "godlike", "global esports", "revenant", "orangutan", "team soul",
               "skyesports", "upthrust", "nodwin", "velocity gaming",
               "true rippers", "medal esports"]

# Throw away anything containing these (deals, guides, leaks of skins etc.)
BLOCK_WORDS = ["redeem code", "redeem codes", "tier list", "how to", "patch notes", "skin",
               "skins", "bundle", "leak", "leaked", "deal", "discount", "sale", "price cut",
               "best settings", "crosshair code", "guide", "wallpaper", "trailer", "review:",
               "betting", "odds", "casino"]

# ---------------------------------------------------------------- feeds
def _gnews(q: str) -> str:
    from urllib.parse import quote
    return ("https://news.google.com/rss/search?q=" + quote(q + " when:1d")
            + "&hl=en-IN&gl=IN&ceid=IN:en")

FEEDS = [
    # Dedicated esports sites (RSS)
    {"name": "Dot Esports", "url": "https://dotesports.com/feed"},
    {"name": "Esports Insider", "url": "https://esportsinsider.com/feed"},
    {"name": "HLTV", "url": "https://www.hltv.org/rss/news"},
    {"name": "Esports.gg", "url": "https://esports.gg/feed/"},
    {"name": "EventHubs", "url": "https://www.eventhubs.com/rss/news/"},
    {"name": "Afk Gaming", "url": "https://afkgaming.com/rss"},
    # Google News searches (very reliable, catches everything else)
    {"name": "GNews Valorant", "url": _gnews('VCT OR "Valorant Champions" OR "Valorant Masters" OR "Valorant esports"')},
    {"name": "GNews CS2", "url": _gnews('"Counter-Strike" OR CS2 (major OR IEM OR BLAST OR esports)')},
    {"name": "GNews Fighting", "url": _gnews('Tekken OR "Street Fighter 6" OR "Mortal Kombat" (EVO OR tournament OR esports OR "Capcom Cup")')},
    {"name": "GNews BGMI", "url": _gnews('BGMI OR BGIS OR BMPS esports')},
    {"name": "GNews India esports", "url": _gnews('India esports tournament')},
    {"name": "GNews Esports", "url": _gnews('esports tournament champion OR final OR "prize pool"')},
    {"name": "GNews LoL Dota", "url": _gnews('"League of Legends" OR "Dota 2" (Worlds OR LCK OR "The International" OR esports)')},
]
