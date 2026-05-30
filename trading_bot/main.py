import time
import schedule
from datetime import datetime

from config import STOCKS, CRYPTO, CHECK_INTERVAL_MINUTES
from data_fetcher import fetch_stock, fetch_crypto
from signal_engine import analyze
from alerts import send_signal, send_telegram

# Garde les signaux déjà envoyés pour éviter le spam (reset chaque jour)
_sent_today: set[str] = set()


def _reset_daily():
    _sent_today.clear()
    print(f"[{datetime.now():%H:%M}] Reset signaux quotidiens")


def _check_all():
    print(f"\n[{datetime.now():%H:%M:%S}] Vérification en cours…")

    for ticker in STOCKS:
        df = fetch_stock(ticker)
        if df is None:
            continue
        signal = analyze(ticker, df, "stock")
        key = f"{ticker}-{signal.action}" if signal else None
        if signal and key not in _sent_today:
            send_signal(signal)
            _sent_today.add(key)
            time.sleep(1)  # évite le rate-limit Telegram

    for coin in CRYPTO:
        df = fetch_crypto(coin)
        if df is None:
            continue
        signal = analyze(coin, df, "crypto")
        key = f"{coin}-{signal.action}" if signal else None
        if signal and key not in _sent_today:
            send_signal(signal)
            _sent_today.add(key)
            time.sleep(1)

    print(f"[{datetime.now():%H:%M:%S}] Vérification terminée.")


def main():
    print("=" * 50)
    print("  Trading Signal Bot — Revolut Alerts")
    print("=" * 50)

    send_telegram("🤖 <b>Bot démarré</b>\nSurveillance active — alertes Achat/Vente en cours.")

    # Lance une première vérification immédiate
    _check_all()

    # Planifie les vérifications suivantes
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(_check_all)
    schedule.every().day.at("00:00").do(_reset_daily)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
