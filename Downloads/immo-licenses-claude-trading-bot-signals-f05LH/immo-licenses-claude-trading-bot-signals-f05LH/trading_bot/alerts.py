import queue
import requests
from datetime import datetime
from typing import Any
from signal_engine import Signal
from config import MODE, WHATSAPP_PHONE, CALLMEBOT_APIKEY

# File d'événements SSE consommée par l'interface web
event_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=200)

STRENGTH_LABEL = {1: "faible", 2: "moyen", 3: "fort"}


def _push_event(data: dict) -> None:
    try:
        event_queue.put_nowait(data)
    except queue.Full:
        event_queue.get_nowait()
        event_queue.put_nowait(data)


def send_message(text: str) -> None:
    _push_event({"type": "log", "text": text, "ts": datetime.now().strftime("%H:%M:%S")})
    if MODE == "phone":
        _send_whatsapp(text)


def _send_whatsapp(text: str) -> bool:
    params = {"phone": WHATSAPP_PHONE, "text": text, "apikey": CALLMEBOT_APIKEY}
    try:
        r = requests.get("https://api.callmebot.com/whatsapp.php", params=params, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"[whatsapp] Erreur: {e}")
        return False


def format_signal(signal: Signal) -> str:
    strength = STRENGTH_LABEL.get(signal.strength, "fort")
    emoji = "✅" if signal.action == "ACHAT" else "🔴"
    reasons_str = "\n".join(f"  - {r}" for r in signal.reasons)
    label = "Action" if signal.asset_type == "stock" else "Crypto"
    return (
        f"{emoji} Signal {signal.action} - {signal.asset.upper()}\n"
        f"Type  : {label} | Prix : {signal.price:,.2f} EUR\n"
        f"RSI   : {signal.rsi:.1f} | Force : {strength} ({signal.strength}/3)\n"
        f"Raisons :\n{reasons_str}\n"
        f"⚠️ Alerte informative - execute manuellement sur Revolut."
    )


def send_signal(signal: Signal) -> None:
    _push_event({
        "type": "signal",
        "asset": signal.asset.upper(),
        "asset_type": signal.asset_type,
        "action": signal.action,
        "price": round(signal.price, 2),
        "rsi": round(signal.rsi, 1),
        "strength": signal.strength,
        "strength_label": STRENGTH_LABEL.get(signal.strength, "fort"),
        "reasons": signal.reasons,
        "ts": datetime.now().strftime("%H:%M:%S"),
    })
    print(f"[alert] {signal.asset} {signal.action} → interface")
    if MODE == "phone":
        _send_whatsapp(format_signal(signal))
