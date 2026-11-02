"""Tiny JSON file memory. Survives restarts if DATA_DIR is on a Railway Volume."""
import json
import os
import threading
import time

import config

_LOCK = threading.RLock()
PATH = os.path.join(config.DATA_DIR, "state.json")

DEFAULT = {
    "mode": config.DEFAULT_MODE,     # review | auto
    "paused": False,
    "seeded": False,                 # first run: remember current news, don't post it
    "seen": {},                      # item_key -> first-seen ts
    "stories": {},                   # story_id -> story dict
    "posted_times": [],              # timestamps of channel posts (rate limit)
    "matches": {},                   # pandascore match id -> last status we announced
    "feed_status": {},               # feed name -> {"ok": bool, "err": str, "ts": float, "items": int}
    "muted_games": [],
    "pending_edit": None,            # story id the admin is currently editing
    "stats": {"posted": 0, "skipped": 0, "auto": 0, "live_alerts": 0},
}


class State:
    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULT))
        self.load()

    def load(self):
        try:
            with open(PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                self.data[k] = v
            for k, v in DEFAULT.items():          # new keys added in updates
                self.data.setdefault(k, json.loads(json.dumps(v)))
        except FileNotFoundError:
            pass
        except Exception as e:  # corrupt file - start fresh but keep a copy
            print(f"[storage] could not read state ({e}); starting fresh")
            try:
                os.replace(PATH, PATH + ".broken")
            except OSError:
                pass

    def save(self):
        with _LOCK:
            os.makedirs(config.DATA_DIR, exist_ok=True)
            self.prune()
            tmp = PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
            os.replace(tmp, PATH)

    def prune(self):
        """Keep the file small: forget things older than 3 days."""
        cutoff = time.time() - 3 * 86400
        self.data["seen"] = {k: t for k, t in self.data["seen"].items() if t > cutoff}
        self.data["stories"] = {k: s for k, s in self.data["stories"].items()
                                if s.get("first_seen", 0) > cutoff}
        hour_ago = time.time() - 3600
        self.data["posted_times"] = [t for t in self.data["posted_times"] if t > hour_ago]
        if len(self.data["matches"]) > 3000:
            items = list(self.data["matches"].items())[-1500:]
            self.data["matches"] = dict(items)

    @property
    def lock(self):
        return _LOCK

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v
