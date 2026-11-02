"""Live match + result alerts from PandaScore (free 'Fixtures' plan is enough).
Only runs if PANDASCORE_TOKEN is set."""
import json
import os
import time
import urllib.request
from datetime import datetime, timezone, timedelta

import config

API = "https://api.pandascore.co"
IST = timezone(timedelta(hours=5, minutes=30))
# Which tournament tiers count as "big". PandaScore tiers: s (top) > a > b > c > d
TOP_TIERS = set(os.getenv("LIVE_TIERS", "s,a").split(","))
SLUG_TO_GAME = {g["pandascore"]: gid for gid, g in config.GAMES.items() if g["pandascore"]}


def _get(path: str):
    req = urllib.request.Request(API + path, headers={
        "Authorization": f"Bearer {config.PANDASCORE_TOKEN}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _game_of(m):
    slug = ((m.get("videogame") or {}).get("slug")) or ""
    return SLUG_TO_GAME.get(slug)


def _is_big(m, gid):
    tier = ((m.get("tournament") or {}).get("tier") or "").lower()
    if config.GAMES[gid]["tier"] == 1:
        return tier in TOP_TIERS
    return tier == "s"


def _teams(m):
    names = []
    for o in m.get("opponents") or []:
        op = o.get("opponent") or {}
        names.append(op.get("name") or op.get("acronym") or "TBD")
    while len(names) < 2:
        names.append("TBD")
    return names


def _event_name(m):
    league = (m.get("league") or {}).get("name") or ""
    serie = (m.get("serie") or {}).get("full_name") or ""
    tour = (m.get("tournament") or {}).get("name") or ""
    ev = " ".join(x for x in (league, serie) if x).strip()
    return f"{ev} – {tour}" if tour else ev


def _stream(m):
    streams = m.get("streams_list") or []
    for s in streams:
        if s.get("main") and s.get("raw_url"):
            return s["raw_url"]
    for s in streams:
        if s.get("language") == "en" and s.get("raw_url"):
            return s["raw_url"]
    return streams[0]["raw_url"] if streams and streams[0].get("raw_url") else ""


def _score(m):
    res = {r.get("team_id"): r.get("score", 0) for r in m.get("results") or []}
    sc = []
    for o in m.get("opponents") or []:
        sc.append(res.get((o.get("opponent") or {}).get("id"), 0))
    return sc


def _story(m, gid, kind, now):
    a, b = _teams(m)
    bo = m.get("number_of_games")
    ev = _event_name(m)
    g = config.GAMES[gid]
    if kind == "live":
        title = f"🔴 LIVE NOW: {a} vs {b}"
        summary = f"{ev}" + (f" · Best of {bo}" if bo else "")
        link = _stream(m)
    else:
        sc = _score(m)
        winner = (m.get("winner") or {}).get("name") or ""
        score_txt = f"{sc[0]}–{sc[1]}" if len(sc) >= 2 else ""
        if winner:
            loser = b if winner == a else a
            title = f"🏁 RESULT: {winner} beat {loser} {score_txt}".strip()
        else:
            title = f"🏁 RESULT: {a} {score_txt} {b}"
        summary = ev
        link = ""
    sid = f"m{m['id']}-{kind}"
    tier1 = g["tier"] == 1
    return {
        "id": sid, "title": title, "summary": summary, "link": link, "links": [link] if link else [],
        "source": "PandaScore", "sources": ["PandaScore"], "image": "", "game": gid,
        "published": now, "first_seen": now, "tokens": [], "status": "new",
        "kind": kind, "instant": True, "score": 90 if tier1 else 65,
        "priority": 1 if tier1 else 2, "big_event": True, "breaking": True, "india": False,
    }


def check(state, now=None, seeding=False):
    """Updates state; returns list of new alert stories (already stored in state['stories'])."""
    if not config.PANDASCORE_TOKEN:
        return []
    now = now or time.time()
    running = _get("/matches/running?per_page=100")
    past = _get("/matches/past?sort=-end_at&per_page=50")
    return apply(running, past, state, now, seeding)


def apply(running, past, state, now, seeding=False):
    """Pure logic (testable without internet)."""
    out = []
    mem = state["matches"]
    for m in running:
        gid = _game_of(m)
        if not gid or gid in state["muted_games"] or not _is_big(m, gid):
            continue
        key = str(m["id"])
        if key not in mem:
            mem[key] = "running"
            if not seeding:
                s = _story(m, gid, "live", now)
                state["stories"][s["id"]] = s
                out.append(s)
    for m in past:
        gid = _game_of(m)
        if not gid or gid in state["muted_games"] or not _is_big(m, gid):
            continue
        if m.get("status") != "finished":
            continue
        key = str(m["id"])
        if mem.get(key) == "finished":
            continue
        end = m.get("end_at")
        recent = False
        if end:
            try:
                recent = now - datetime.fromisoformat(end.replace("Z", "+00:00")).timestamp() < 3 * 3600
            except ValueError:
                pass
        if mem.get(key) == "running" or recent:
            mem[key] = "finished"
            if not seeding:
                s = _story(m, gid, "result", now)
                state["stories"][s["id"]] = s
                out.append(s)
    return out


def running_now(state):
    """For /live: list of text lines."""
    if not config.PANDASCORE_TOKEN:
        return None
    lines = []
    for m in _get("/matches/running?per_page=100"):
        gid = _game_of(m)
        if not gid:
            continue
        a, b = _teams(m)
        sc = _score(m)
        tier = ((m.get("tournament") or {}).get("tier") or "?").upper()
        g = config.GAMES[gid]
        lines.append((g["tier"], f"{g['emoji']} <b>{a} {sc[0] if sc else 0}–{sc[1] if len(sc) > 1 else 0} {b}</b>"
                      f"\n    {_event_name(m)} · Tier {tier}"))
    lines.sort(key=lambda x: x[0])
    return [l for _, l in lines[:20]]


def upcoming_today(hours=24):
    if not config.PANDASCORE_TOKEN:
        return None
    now = datetime.now(timezone.utc)
    lines = []
    for m in _get("/matches/upcoming?sort=begin_at&per_page=100"):
        gid = _game_of(m)
        if not gid or not _is_big(m, gid) or not m.get("begin_at"):
            continue
        t = datetime.fromisoformat(m["begin_at"].replace("Z", "+00:00"))
        if t - now > timedelta(hours=hours):
            continue
        a, b = _teams(m)
        g = config.GAMES[gid]
        lines.append((t, f"🕒 <b>{t.astimezone(IST):%I:%M %p}</b> {g['emoji']} {a} vs {b}\n    {_event_name(m)}"))
    lines.sort(key=lambda x: x[0])
    return [l for _, l in lines[:25]]
