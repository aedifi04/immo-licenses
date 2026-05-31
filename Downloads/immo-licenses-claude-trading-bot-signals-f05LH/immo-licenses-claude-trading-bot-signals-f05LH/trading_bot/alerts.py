import requests
from signal_engine import Signal
from config import WHATSAPP_PHONE, CALLMEBOT_APIKEY

EMOJI = {"ACHAT": "✅", "VENTE": "🔴"}
STRENGTH_LABEL = {1: "faible", 2: "moyen", 3: "fort"}


def send_message(text: str) -> bool:
    params = {"phone": WHATSAPP_PHONE, "text": text, "apikey": CALLMEBOT_APIKEY}
    try:
        r = requests.get("https://api.callmebot.com/whatsapp.php", params=params, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"[whatsapp] Erreur: {e}")
        return False


def format_signal(signal: Signal) -> str:
    strength = STRENGTH_LABEL.get(signal.strength, "fort")
    emoji = EMOJI[signal.action]
    reasons_str = "\n".join(f"  - {r}" for r in signal.reasons)
    label = "Action" if signal.asset_type == "stock" else "Crypto"

    return (
        f"{emoji} Signal {signal.action} - {signal.asset.upper()}\n"
        f"Type  : {label}\n"
        f"Prix  : {signal.price:,.2f} EUR\n"
        f"RSI   : {signal.rsi:.1f}\n"
        f"Force : {strength} ({signal.strength}/3)\n"
        f"\nRaisons :\n{reasons_str}\n"
        f"\n⚠️ Alerte informative - execute manuellement sur Revolut."
    )


def send_signal(signal: Signal) -> None:
    ok = send_message(format_signal(signal))
    print(f"[alert] {signal.asset} {signal.action} → WhatsApp {'OK' if ok else 'ECHEC'}")
