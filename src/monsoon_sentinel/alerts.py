"""WhatsApp / SMS alert delivery.

Providers (picked from environment variables; nothing is sent without them):
  SMS       Twilio            TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_SMS_FROM
  WhatsApp  Meta Cloud API    WA_TOKEN, WA_PHONE_NUMBER_ID, WA_TEMPLATE (+ WA_TEMPLATE_LANG, WA_API_VERSION)
            or Twilio         TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM (e.g. whatsapp:+14155238886)
With MS_ALERTS_DRY_RUN=1 (or no provider configured) messages are only logged.

Business-initiated WhatsApp messages need an approved template; free-form text works only
inside the 24 h window after the user messages you (e.g. Twilio's sandbox after "join ...").
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import requests

from monsoon_sentinel import telegram

PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
ALERT_RANK = {"green": 0, "yellow": 1, "orange": 2, "red": 3}

TITLES = {
    "en": {"yellow": "YELLOW alert (be aware)", "orange": "ORANGE alert (be prepared)", "red": "RED alert (take action)"},
    "mr": {"yellow": "पिवळा इशारा (सावध रहा)", "orange": "नारिंगी इशारा (तयार रहा)", "red": "लाल इशारा (कृती करा)"},
    "hi": {"yellow": "पीली चेतावनी (सतर्क रहें)", "orange": "नारंगी चेतावनी (तैयार रहें)", "red": "लाल चेतावनी (कार्रवाई करें)"},
}
ADVICE = {
    "en": {"yellow": "Water may collect on low roads.", "orange": "Waterlogging likely; avoid low-lying roads and underpasses.",
           "red": "Severe waterlogging expected; avoid travel on red streets."},
    "mr": {"yellow": "सखल रस्त्यांवर पाणी साचू शकते.", "orange": "पाणी साचण्याची शक्यता; सखल भाग व भुयारी मार्ग टाळा.",
           "red": "मोठ्या प्रमाणात पाणी साचेल; लाल रस्त्यांवर प्रवास टाळा."},
    "hi": {"yellow": "निचली सड़कों पर पानी जमा हो सकता है।", "orange": "जलभराव की संभावना; निचले हिस्सों व अंडरपास से बचें।",
           "red": "गंभीर जलभराव की आशंका; लाल सड़कों पर यात्रा से बचें।"},
}
WORDS = {
    "en": {"chance": "Heavy-rain chance", "stop": "Stop alerts", "code": "Your Monsoon Sentinel code is",
           "welcome": "You will get Monsoon Sentinel rain alerts for"},
    "mr": {"chance": "मुसळधार पावसाची शक्यता", "stop": "इशारे बंद करा", "code": "तुमचा मान्सून सेंटिनेल कोड",
           "welcome": "तुम्हाला यासाठी पावसाचे इशारे मिळतील:"},
    "hi": {"chance": "भारी बारिश की संभावना", "stop": "अलर्ट बंद करें", "code": "आपका मानसून सेंटिनल कोड",
           "welcome": "आपको इसके लिए बारिश के अलर्ट मिलेंगे:"},
}


def alert_text(lang: str, alert: str, place: str, road: str, prob: float, link: str, unsub: str) -> str:
    lang = lang if lang in TITLES else "en"
    w = WORDS[lang]
    return (f"Monsoon Sentinel · {TITLES[lang][alert]}\n{place} ({road})\n{ADVICE[lang][alert]}\n"
            f"{w['chance']}: {round(prob * 100)}%\n{link}\n{w['stop']}: {unsub}")


def code_text(lang: str, code: str) -> str:
    return f"{WORDS.get(lang, WORDS['en'])['code']}: {code}"


@dataclass
class SendResult:
    status: str            # sent | dry_run | failed
    provider: str
    provider_id: str | None = None
    detail: str | None = None


def dry_run() -> bool:
    return os.environ.get("MS_ALERTS_DRY_RUN", "0") == "1"


def configured() -> dict:
    e = os.environ
    return {
        "sms_twilio": all(e.get(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_SMS_FROM")),
        "whatsapp_meta": all(e.get(k) for k in ("WA_TOKEN", "WA_PHONE_NUMBER_ID")),
        "whatsapp_twilio": all(e.get(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM")),
        "telegram": telegram.configured(),
        "dry_run": dry_run(),
    }


# WhatsApp only allows free-form text inside the 24 h window after the user writes to you;
# business-initiated messages need an approved template, sent by its Content SID (HX...).
TEMPLATE_ERRORS = ("21654", "63016", "63032")
TWILIO_TEMPLATE_ENV = {"code": "TWILIO_WA_CODE_CONTENT_SID", "alert": "TWILIO_WA_ALERT_CONTENT_SID"}


def _twilio(to: str, body: str, sender: str, content_sid: str | None = None,
            variables: list[str] | None = None) -> SendResult:
    sid, tok = os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]
    data = {"To": to, "From": sender}
    if content_sid:
        data["ContentSid"] = content_sid
        data["ContentVariables"] = json.dumps({str(i + 1): str(v) for i, v in enumerate(variables or [])})
    else:
        data["Body"] = body
    r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                      data=data, auth=(sid, tok), timeout=30)
    if r.ok:
        return SendResult("sent", "twilio", r.json().get("sid"))
    return SendResult("failed", "twilio", detail=f"{r.status_code}: {r.text[:200]}")


def _twilio_whatsapp(to: str, body: str, kind: str, template_params: list[str] | None) -> SendResult:
    """Template first when one is configured for this kind of message, else free-form text."""
    sender = os.environ["TWILIO_WHATSAPP_FROM"]
    content_sid = os.environ.get(TWILIO_TEMPLATE_ENV.get(kind, ""), "").strip()
    if content_sid and template_params is not None:
        return _twilio(f"whatsapp:{to}", body, sender, content_sid, template_params)
    res = _twilio(f"whatsapp:{to}", body, sender)
    if res.status == "failed" and any(c in (res.detail or "") for c in TEMPLATE_ERRORS):
        env = TWILIO_TEMPLATE_ENV.get(kind)
        res.detail = ("WhatsApp only accepts an approved template for this message. "
                      + (f"Set {env} to the template's Content SID (HX...)." if env else "Ask the user to message first."))
    return res


def _meta_whatsapp(to: str, body: str, template_params: list[str] | None) -> SendResult:
    e = os.environ
    url = f"https://graph.facebook.com/{e.get('WA_API_VERSION', 'v21.0')}/{e['WA_PHONE_NUMBER_ID']}/messages"
    if e.get("WA_TEMPLATE") and template_params is not None:
        payload = {"messaging_product": "whatsapp", "to": to.lstrip("+"), "type": "template",
                   "template": {"name": e["WA_TEMPLATE"], "language": {"code": e.get("WA_TEMPLATE_LANG", "en")},
                                "components": [{"type": "body", "parameters": [
                                    {"type": "text", "text": p} for p in template_params]}]}}
    else:  # free-form text: only delivered inside the 24 h customer-service window
        payload = {"messaging_product": "whatsapp", "to": to.lstrip("+"), "type": "text", "text": {"body": body}}
    r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {e['WA_TOKEN']}"}, timeout=30)
    if r.ok:
        msgs = r.json().get("messages") or [{}]
        return SendResult("sent", "meta_whatsapp", msgs[0].get("id"))
    return SendResult("failed", "meta_whatsapp", detail=f"{r.status_code}: {r.text[:200]}")


def send(channel: str, to: str, body: str, template_params: list[str] | None = None,
         kind: str = "info", buttons: list[tuple[str, str]] | None = None) -> SendResult:
    """kind: "code" (verification), "alert" (morning alert) or "info" (free-form only)."""
    cfg = configured()
    if cfg["dry_run"]:
        return SendResult("dry_run", "log", detail=body[:160])
    try:
        if channel == "sms" and cfg["sms_twilio"]:
            return _twilio(to, body, os.environ["TWILIO_SMS_FROM"])
        if channel == "whatsapp" and cfg["whatsapp_meta"]:
            return _meta_whatsapp(to, body, template_params)
        if channel == "whatsapp" and cfg["whatsapp_twilio"]:
            return _twilio_whatsapp(to, body, kind, template_params)
        if channel == "telegram" and cfg["telegram"]:
            try:
                return SendResult("sent", "telegram", telegram.send_message(to, body, buttons))
            except RuntimeError as ex:
                return SendResult("failed", "telegram", detail=str(ex)[:200])
    except requests.RequestException as ex:
        return SendResult("failed", channel, detail=str(ex)[:200])
    return SendResult("dry_run", "log", detail="no provider configured for " + channel)


def mask(phone: str) -> str:
    return phone[:3] + "•" * max(len(phone) - 7, 0) + phone[-4:]
