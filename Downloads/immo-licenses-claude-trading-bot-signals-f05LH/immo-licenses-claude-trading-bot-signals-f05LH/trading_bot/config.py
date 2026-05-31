# ─── Mode ─────────────────────────────────────────────────────────────────────
MODE = "pc"   # "pc" = interface seule | "phone" = WhatsApp + interface

# ─── WhatsApp (si MODE = "phone") ─────────────────────────────────────────────
WHATSAPP_PHONE   = "+33612345678"
CALLMEBOT_APIKEY = "TON_APIKEY"

# ─── Interface web ────────────────────────────────────────────────────────────
WEB_PORT = 5000

# ─── Assets à surveiller ─────────────────────────────────────────────────────
STOCKS = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN"]

CRYPTO = ["bitcoin", "ethereum", "solana", "ripple"]

# Correspondance nom → symbole Binance (USDT)
CRYPTO_BINANCE: dict[str, str] = {
    "bitcoin":  "BTCUSDT",
    "ethereum": "ETHUSDT",
    "solana":   "SOLUSDT",
    "ripple":   "XRPUSDT",
}

# ─── Indicateurs ──────────────────────────────────────────────────────────────
RSI_PERIOD     = 14
RSI_OVERSOLD   = 38    # < 30 était trop rare → plus de signaux
RSI_OVERBOUGHT = 62

MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9

EMA_SHORT = 9
EMA_LONG  = 21

MOMENTUM_PERIODS   = 3    # variation sur les 3 dernières bougies
MOMENTUM_THRESHOLD = 0.8  # % de variation pour déclencher le signal

# ─── Timeframe ─────────────────────────────────────────────────────────────────
# 1h = signaux intraday, réactifs aux mouvements de 30-60 min
CHECK_INTERVAL_MINUTES = 30
STOCK_INTERVAL = "1h"
STOCK_PERIOD   = "7d"
CRYPTO_INTERVAL = "1h"
CRYPTO_LIMIT    = 100   # 100 dernières bougies 1h
