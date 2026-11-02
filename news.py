"""Fetch esports news feeds, work out which game each story is about, score it,
and merge the same story coming from different websites."""
import gzip
import hashlib
import html
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import config

UA = "Mozilla/5.0 (compatible; NXTEsportsBot/1.0; +https://t.me/)"
MEDIA_NS = "{http://search.yahoo.com/mrss/}"
ATOM_NS = "{http://www.w3.org/2005/Atom}"

STOP = set("""a an the and or of to in on for at by with from is are was were be been
as it its this that after before over into vs v about their his her they he she we you
new news report reports says say said will can could may just more most first last
day week year 2025 2026 2027 up out off how why what who when where amid against""".split())


# ----------------------------------------------------------------- helpers
def http_get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return data


def clean_text(s: str) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def _word_re(words):
    words = sorted(set(w.lower() for w in words), key=len, reverse=True)
    return re.compile(r"(?<![\w])(" + "|".join(re.escape(w) for w in words) + r")(?![\w])", re.I)


GAME_RES = {gid: _word_re(g["words"]) for gid, g in config.GAMES.items()}
GENERAL_RE = _word_re(config.GENERAL_WORDS)
BIG_RE = _word_re(config.BIG_EVENTS)
BREAKING_RE = _word_re(config.BREAKING_WORDS)
INDIA_RE = _word_re(config.INDIA_WORDS)
BLOCK_RE = _word_re(config.BLOCK_WORDS)


def _parse_date(s: str):
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


# ----------------------------------------------------------------- parsing
def parse_feed(raw: bytes, feed_name: str):
    """Returns a list of dicts: title, summary, link, source, published, image."""
    root = ET.fromstring(raw)
    out = []
    items = root.iter("item")
    is_atom = False
    items = list(items)
    if not items:
        items = list(root.iter(ATOM_NS + "entry"))
        is_atom = True
    for it in items:
        def t(tag):
            el = it.find(tag)
            return (el.text or "") if el is not None else ""
        if is_atom:
            title = t(ATOM_NS + "title")
            link_el = it.find(ATOM_NS + "link")
            link = link_el.get("href", "") if link_el is not None else ""
            summary = t(ATOM_NS + "summary") or t(ATOM_NS + "content")
            pub = t(ATOM_NS + "updated") or t(ATOM_NS + "published")
        else:
            title, link = t("title"), t("link").strip()
            summary = t("description")
            pub = t("pubDate") or t("{http://purl.org/dc/elements/1.1/}date")
        title = clean_text(title)
        source = feed_name
        src_el = it.find("source")
        if src_el is not None and (src_el.text or "").strip():
            source = src_el.text.strip()
        # Google News puts " - Publisher" at the end of the title
        if feed_name.startswith("GNews") and " - " in title:
            head, _, pub_name = title.rpartition(" - ")
            if head and len(pub_name) < 60:
                title = head
                if source == feed_name:
                    source = pub_name
        if feed_name.startswith("GNews"):
            summary = ""  # Google's description is just the title again
        image = ""
        for tag in (MEDIA_NS + "content", MEDIA_NS + "thumbnail"):
            el = it.find(tag)
            if el is not None and el.get("url"):
                image = el.get("url")
                break
        if not image:
            enc = it.find("enclosure")
            if enc is not None and "image" in (enc.get("type") or "") and enc.get("url"):
                image = enc.get("url")
        if not title:
            continue
        out.append({
            "title": title,
            "summary": clean_text(summary)[:400],
            "link": link,
            "source": source,
            "published": _parse_date(pub),
            "image": image,
        })
    return out


def fetch_all(feeds=None):
    """Fetch every feed in parallel. Returns (items, status_by_feed)."""
    feeds = feeds or config.FEEDS
    items, status = [], {}

    def one(feed):
        try:
            got = parse_feed(http_get(feed["url"]), feed["name"])
            return feed["name"], got, None
        except Exception as e:  # one broken site must never stop the bot
            return feed["name"], [], f"{type(e).__name__}: {str(e)[:120]}"

    with ThreadPoolExecutor(max_workers=8) as ex:
        for name, got, err in ex.map(one, feeds):
            status[name] = {"ok": err is None, "err": err or "", "items": len(got), "ts": time.time()}
            items.extend(got)
    return items, status


# ----------------------------------------------------------------- classify + score
def classify(title: str, summary: str = ""):
    """Return (game_id or 'general' or None, details dict)."""
    text = f"{title} {summary}"
    if BLOCK_RE.search(title):
        return None, {}
    best, best_hits = None, 0
    for gid, rx in GAME_RES.items():
        hits_title = len(rx.findall(title))
        hits = hits_title * 3 + len(rx.findall(summary))
        if hits > best_hits:
            best, best_hits = gid, hits
    if best is None and GENERAL_RE.search(text):
        best = "general"
    if best is None:
        return None, {}
    return best, {
        "big_event": bool(BIG_RE.search(title)),
        "breaking": bool(BREAKING_RE.search(title)),
        "india": bool(INDIA_RE.search(text)),
    }


def score_story(s: dict, now: float = None) -> None:
    """Fills s['score'] and s['priority'] (1 = biggest)."""
    now = now or time.time()
    g = config.GAMES.get(s["game"])
    tier = g["tier"] if g else 3
    score = {1: 40, 2: 25, 3: 12}[tier] if g else 10
    if s.get("big_event"):
        score += 25
    if s.get("breaking"):
        score += 15
    if s.get("india"):
        score += 15
    score += min(20, 10 * (len(s["sources"]) - 1))
    age_h = (now - (s.get("published") or s["first_seen"])) / 3600
    if age_h < 1:
        score += 10
    elif age_h < 3:
        score += 5
    s["score"] = score
    s["priority"] = 1 if score >= 80 else 2 if score >= 60 else 3 if score >= 40 else 4


def tokens(title: str):
    words = re.findall(r"[a-z0-9]+", title.lower())
    return sorted({w for w in words if w not in STOP and len(w) > 1})


def same_story(a_tok, b_tok) -> bool:
    a, b = set(a_tok), set(b_tok)
    if not a or not b:
        return False
    inter = len(a & b)
    if inter / len(a | b) >= 0.5:
        return True
    small = min(len(a), len(b))
    return small >= 4 and inter / small >= 0.75


def item_key(it) -> str:
    base = (it.get("link") or "") + "|" + it["title"].lower()
    return hashlib.sha1(base.encode()).hexdigest()[:16]


# ----------------------------------------------------------------- main step
def process(items, state, now=None):
    """Merge freshly fetched items into state['stories'].
    Returns list of story ids that are new or changed this round."""
    now = now or time.time()
    seen = state["seen"]
    stories = state["stories"]
    changed = []
    max_age = config.MAX_AGE_HOURS * 3600
    for it in items:
        k = item_key(it)
        if k in seen:
            continue
        seen[k] = now
        if it["published"] and now - it["published"] > max_age:
            continue
        game, info = classify(it["title"], it["summary"])
        if game is None or game in state["muted_games"]:
            continue
        tok = tokens(it["title"])
        match = None
        for sid, s in stories.items():
            if now - s["first_seen"] > 24 * 3600:
                continue
            if s["game"] not in (game, "general") and game != "general":
                continue
            if same_story(tok, s["tokens"]):
                match = sid
                break
        if match:
            s = stories[match]
            if it["source"] not in s["sources"]:
                s["sources"].append(it["source"])
                s["links"].append(it["link"])
                if not s.get("image") and it["image"]:
                    s["image"] = it["image"]
                if not s.get("summary") and it["summary"]:
                    s["summary"] = it["summary"]
                for f in ("big_event", "breaking", "india"):
                    s[f] = s.get(f) or info.get(f, False)
                score_story(s, now)
                changed.append(match)
            continue
        sid = k
        s = {
            "id": sid, "title": it["title"], "summary": it["summary"], "link": it["link"],
            "links": [it["link"]], "source": it["source"], "sources": [it["source"]],
            "image": it["image"], "game": game, "published": it["published"],
            "first_seen": now, "tokens": tok, "status": "new", **info,
        }
        score_story(s, now)
        stories[sid] = s
        changed.append(sid)
    return changed


def ready_to_send(state, now=None):
    """Stories that are new and have waited long enough (P1 goes immediately)."""
    now = now or time.time()
    out = []
    for s in state["stories"].values():
        if s["status"] != "new":
            continue
        waited = now - s["first_seen"]
        if s["priority"] == 1 or waited >= config.HOLD_MINUTES * 60:
            out.append(s)
    out.sort(key=lambda s: (s["priority"], -s["score"]))
    return out
