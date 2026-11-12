"""Telegram bot channel for alerts (free, no message templates, instant opt-in).

Sign-up flow: the website creates a pending subscription and shows a deep link
t.me/<bot>?start=<token>. When the person presses Start, Telegram calls our webhook
with "/start <token>"; we link that chat to the subscription and activate it.
Telegram itself proves the account, so no verification code is needed.

Environment: TELEGRAM_BOT_TOKEN (from @BotFather). Optional TELEGRAM_BOT_USERNAME
(otherwise read once from getMe).
"""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache

import requests

API = "https://api.telegram.org/bot{token}/{method}"

TEXT = {
    "en": {
        "welcome": "✅ You're subscribed to Monsoon Sentinel alerts for {place}.\nYou'll get a message on mornings when this street is at {level} or worse.\n\nCommands: /status · /stop",
        "already": "You're already subscribed for {place}.",
        "unknown_link": "This sign-up link has expired. Please open the Monsoon Sentinel website and tap 'Get alerts' again.",
        "hello": "Hi! I send street-level waterlogging alerts for Pune. Sign up on the website to choose your street.",
        "stopped": "🛑 Alerts stopped for all your places. You can sign up again anytime on the website.",
        "status_none": "You have no active alert subscriptions.",
        "status": "Your alert places:\n{items}",
        "open_map": "Open map",
        "stop": "Stop alerts",
        "levels": {"yellow": "yellow", "orange": "orange", "red": "red"},
    },
    "mr": {
        "welcome": "✅ {place} साठी मान्सून सेंटिनेल इशाऱ्यांची नोंदणी झाली.\nहा रस्ता {level} किंवा अधिक धोक्यात असेल त्या सकाळी तुम्हाला संदेश मिळेल.\n\nआदेश: /status · /stop",
        "already": "{place} साठी तुमची नोंदणी आधीच झाली आहे.",
        "unknown_link": "ही नोंदणी लिंक कालबाह्य झाली आहे. कृपया वेबसाइटवर पुन्हा 'इशारे मिळवा' टॅप करा.",
        "hello": "नमस्कार! मी पुण्यासाठी रस्ता-स्तरीय पाणी साचण्याचे इशारे पाठवतो. तुमचा रस्ता निवडण्यासाठी वेबसाइटवर नोंदणी करा.",
        "stopped": "🛑 तुमच्या सर्व ठिकाणांचे इशारे बंद केले. वेबसाइटवर केव्हाही पुन्हा नोंदणी करू शकता.",
        "status_none": "तुमची कोणतीही सक्रिय नोंदणी नाही.",
        "status": "तुमची इशारा ठिकाणे:\n{items}",
        "open_map": "नकाशा उघडा",
        "stop": "इशारे बंद करा",
        "levels": {"yellow": "पिवळा", "orange": "नारिंगी", "red": "लाल"},
    },
    "hi": {
        "welcome": "✅ {place} के लिए मानसून सेंटिनल अलर्ट की सदस्यता हो गई।\nजिस सुबह यह सड़क {level} या उससे अधिक ख़तरे में होगी, आपको संदेश मिलेगा।\n\nकमांड: /status · /stop",
        "already": "{place} के लिए आपकी सदस्यता पहले से है।",
        "unknown_link": "यह साइन-अप लिंक समाप्त हो गया है। कृपया वेबसाइट पर फिर से 'अलर्ट पाएँ' दबाएँ।",
        "hello": "नमस्ते! मैं पुणे के लिए सड़क-स्तर पर जलभराव अलर्ट भेजता हूँ। अपनी सड़क चुनने के लिए वेबसाइट पर साइन अप करें।",
        "stopped": "🛑 आपकी सभी जगहों के अलर्ट बंद कर दिए गए। आप वेबसाइट पर कभी भी फिर से साइन अप कर सकते हैं।",
        "status_none": "आपकी कोई सक्रिय सदस्यता नहीं है।",
        "status": "आपकी अलर्ट जगहें:\n{items}",
        "open_map": "नक्शा खोलें",
        "stop": "अलर्ट बंद करें",
        "levels": {"yellow": "पीली", "orange": "नारंगी", "red": "लाल"},
    },
}


def t(lang: str, key: str, **kw) -> str:
    d = TEXT.get(lang, TEXT["en"])
    return d.get(key, TEXT["en"][key]).format(**kw) if kw else d.get(key, TEXT["en"][key])


def token() -> str | None:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    return tok or None


def configured() -> bool:
    return token() is not None


def webhook_secret() -> str:
    """Deterministic secret Telegram echoes in X-Telegram-Bot-Api-Secret-Token."""
    return hashlib.sha256(("ms-webhook:" + (token() or "")).encode()).hexdigest()[:48]


def _call(method: str, **payload) -> dict:
    r = requests.post(API.format(token=token(), method=method), json=payload, timeout=20)
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if not r.ok or not data.get("ok"):
        raise RuntimeError(f"telegram {method} failed: {r.status_code} {str(data)[:200]}")
    return data["result"]


@lru_cache(maxsize=1)
def bot_username() -> str | None:
    if os.environ.get("TELEGRAM_BOT_USERNAME"):
        return os.environ["TELEGRAM_BOT_USERNAME"].lstrip("@")
    if not configured():
        return None
    try:
        return _call("getMe")["username"]
    except Exception:  # noqa: BLE001
        return None


def deep_link(start_token: str) -> str | None:
    u = bot_username()
    return f"https://t.me/{u}?start={start_token}" if u else None


def set_webhook(url: str) -> bool:
    _call("setWebhook", url=url, secret_token=webhook_secret(), allowed_updates=["message"],
          drop_pending_updates=False)
    _call("setMyCommands", commands=[{"command": "status", "description": "Show my alert places"},
                                     {"command": "stop", "description": "Stop all alerts"}])
    return True


def send_message(chat_id: str, text: str, buttons: list[tuple[str, str]] | None = None) -> str:
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": b, "url": u}] for b, u in buttons]}
    return str(_call("sendMessage", **payload).get("message_id"))
