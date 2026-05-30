import requests
from signal_engine import Signal
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

EMOJI = {"ACHAT": "🟢", "VENTE": "🔴"}
STRENGTH_LABEL = {1: "faible", 2: "moyen", 3: "fort"}


def send_telegram(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[telegram] Erreur envoi: {e}")
        return False


def format_signal(signal: Signal) -> str:
    emoji = EMOJI[signal.action]
    strength = STRENGTH_LABEL.get(signal.strength, "fort")
    reasons_str = "\n".join(f"  • {r}" for r in signal.reasons)
    label = "action" if signal.asset_type == "stock" else "crypto"

    return (
        f"{emoji} <b>Signal {signal.action} — {signal.asset.upper()}</b>\n"
        f"Type : {label}\n"
        f"Prix : <b>{signal.price:,.2f} €</b>\n"
        f"RSI  : {signal.rsi:.1f}\n"
        f"Force du signal : {strength} ({signal.strength}/3)\n"
        f"\nRaisons :\n{reasons_str}\n"
        f"\n⚠️ <i>Ceci est une alerte informative, pas un conseil financier.\n"
        f"Exécute manuellement sur Revolut.</i>"
    )


def send_signal(signal: Signal) -> None:
    message = format_signal(signal)
    ok = send_telegram(message)
    status = "envoyée" if ok else "ECHEC"
    print(f"[alert] {signal.asset} {signal.action} → Telegram {status}")
