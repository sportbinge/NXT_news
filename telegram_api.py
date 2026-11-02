"""Minimal Telegram Bot API client using only the Python standard library."""
import json
import time
import urllib.error
import urllib.request

import config


class TelegramError(Exception):
    pass


BASE = "https://api.telegram.org/bot{token}/{method}"


def call(method: str, _timeout: int = 40, **params):
    params = {k: v for k, v in params.items() if v is not None}
    data = json.dumps(params).encode()
    url = BASE.format(token=config.BOT_TOKEN, method=method)
    for attempt in range(3):
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=_timeout) as r:
                res = json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                res = json.loads(e.read())
            except Exception:
                raise TelegramError(f"{method}: HTTP {e.code}") from None
        if res.get("ok"):
            return res["result"]
        wait = (res.get("parameters") or {}).get("retry_after")
        if res.get("error_code") == 429 and wait and attempt < 2:
            time.sleep(min(int(wait) + 1, 60))
            continue
        raise TelegramError(f"{method}: {res.get('description')}")
    raise TelegramError(f"{method}: too many retries")


def send(chat_id, text, buttons=None, image=None, silent=False, preview=True):
    """Send text (HTML). If image URL given, try a photo post first and fall back to text."""
    markup = {"inline_keyboard": buttons} if buttons else None
    if image and len(text) <= 1024:
        try:
            return call("sendPhoto", chat_id=chat_id, photo=image, caption=text,
                        parse_mode="HTML", reply_markup=markup, disable_notification=silent)
        except TelegramError:
            pass  # bad/blocked image URL - send as text instead
    return call("sendMessage", chat_id=chat_id, text=text[:4096], parse_mode="HTML",
                reply_markup=markup, disable_notification=silent,
                link_preview_options={"is_disabled": not preview})


def set_buttons(chat_id, message_id, buttons):
    try:
        call("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id,
             reply_markup={"inline_keyboard": buttons or []})
    except TelegramError as e:
        if "not modified" not in str(e):
            print("[tg]", e)


def answer(callback_id, text=""):
    try:
        call("answerCallbackQuery", callback_query_id=callback_id, text=text[:190])
    except TelegramError:
        pass
