import asyncio
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import STOCKS, CRYPTO, CHECK_INTERVAL_MINUTES, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from data_fetcher import fetch_stock, fetch_crypto
from signal_engine import analyze
from alerts import send_signal, send_message

# ─── État global ──────────────────────────────────────────────────────────────
state = {
    "paused": False,
    "last_scan": None,
    "signals_today": 0,
    "sent_keys": set(),
}


# ─── Scan principal ───────────────────────────────────────────────────────────

async def run_scan(triggered_by: str = "auto") -> int:
    now = datetime.now()
    state["last_scan"] = now
    found = 0

    print(f"\n[{now:%H:%M:%S}] Scan ({triggered_by})…")

    for ticker in STOCKS:
        df = await asyncio.to_thread(fetch_stock, ticker)
        if df is None:
            continue
        signal = analyze(ticker, df, "stock")
        if signal:
            key = f"{ticker}-{signal.action}-{now.date()}"
            if key not in state["sent_keys"]:
                await send_signal(signal)
                state["sent_keys"].add(key)
                state["signals_today"] += 1
                found += 1
                await asyncio.sleep(0.5)

    for coin in CRYPTO:
        df = await asyncio.to_thread(fetch_crypto, coin)
        if df is None:
            continue
        signal = analyze(coin, df, "crypto")
        if signal:
            key = f"{coin}-{signal.action}-{now.date()}"
            if key not in state["sent_keys"]:
                await send_signal(signal)
                state["sent_keys"].add(key)
                state["signals_today"] += 1
                found += 1
                await asyncio.sleep(0.5)

    print(f"[{now:%H:%M:%S}] Scan terminé — {found} signal(s) trouvé(s).")
    return found


# ─── Boucle automatique ───────────────────────────────────────────────────────

async def scheduler_loop():
    await asyncio.sleep(5)  # laisse le bot démarrer
    while True:
        await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)
        if not state["paused"]:
            found = await run_scan("auto")
            if found == 0:
                print(f"[scheduler] Aucun signal — prochain check dans {CHECK_INTERVAL_MINUTES} min")


# ─── Commandes Telegram ───────────────────────────────────────────────────────

def _only_owner(func):
    """Ignore les commandes qui ne viennent pas de toi."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID):
            return
        return await func(update, context)
    return wrapper


@_only_owner
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Trading Signal Bot actif</b>\n\n"
        "Commandes disponibles :\n"
        "/scan — force un scan immédiat\n"
        "/status — état du bot\n"
        "/pause — met en pause les scans auto\n"
        "/resume — reprend les scans auto\n"
        "/watchlist — liste des actifs surveillés",
        parse_mode="HTML"
    )


@_only_owner
async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Scan en cours…")
    found = await run_scan("manuel")
    if found == 0:
        await update.message.reply_text("✅ Scan terminé — aucun signal pour le moment.")
    else:
        await update.message.reply_text(f"✅ Scan terminé — {found} signal(s) envoyé(s).")


@_only_owner
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    paused = "⏸ En pause" if state["paused"] else "▶️ Actif"
    last = state["last_scan"].strftime("%H:%M:%S") if state["last_scan"] else "jamais"
    await update.message.reply_text(
        f"<b>État du bot</b>\n"
        f"Statut : {paused}\n"
        f"Dernier scan : {last}\n"
        f"Signaux envoyés aujourd'hui : {state['signals_today']}\n"
        f"Intervalle : toutes les {CHECK_INTERVAL_MINUTES} min",
        parse_mode="HTML"
    )


@_only_owner
async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state["paused"] = True
    await update.message.reply_text("⏸ Scans automatiques mis en pause.\nUtilise /resume pour reprendre.")


@_only_owner
async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state["paused"] = False
    await update.message.reply_text("▶️ Scans automatiques repris.")


@_only_owner
async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stocks_str = "\n".join(f"  • {s}" for s in STOCKS)
    crypto_str = "\n".join(f"  • {c.capitalize()}" for c in CRYPTO)
    await update.message.reply_text(
        f"<b>Actifs surveillés</b>\n\n"
        f"📈 <b>Actions</b>\n{stocks_str}\n\n"
        f"🪙 <b>Crypto</b>\n{crypto_str}",
        parse_mode="HTML"
    )


# ─── Point d'entrée ───────────────────────────────────────────────────────────

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))

    await send_message(
        "🤖 <b>Bot démarré</b>\n"
        f"Surveillance active toutes les {CHECK_INTERVAL_MINUTES} min.\n"
        "Tape /start pour voir les commandes disponibles."
    )

    # Scan immédiat au démarrage
    await run_scan("démarrage")

    # Lance le scheduler en arrière-plan
    asyncio.create_task(scheduler_loop())

    # Démarre le polling Telegram
    await app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())
