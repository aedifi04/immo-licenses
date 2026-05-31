from telegram import Bot
from signal_engine import Signal
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

EMOJI = {"ACHAT": "🟢", "VENTE": "🔴"}
STRENGTH_LABEL = {1: "faible", 2: "moyen", 3: "fort"}

_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=TELEGRAM_TOKEN)
    return _bot


async def send_message(text: str) -> None:
    await get_bot().send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="HTML")


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
        f"\n⚠️ <i>Alerte informative — exécute manuellement sur Revolut.</i>"
    )


async def send_signal(signal: Signal) -> None:
    await send_message(format_signal(signal))
    print(f"[alert] {signal.asset} {signal.action} → Telegram OK")
