# ─── Mode ─────────────────────────────────────────────────────────────────────
# "pc"    → interface desktop uniquement, pas de WhatsApp
# "phone" → alertes WhatsApp + interface mobile
MODE = "pc"

# ─── WhatsApp (CallMeBot) — uniquement si MODE = "phone" ──────────────────────
WHATSAPP_PHONE   = "+33612345678"
CALLMEBOT_APIKEY = "TON_APIKEY"

# ─── Interface web ────────────────────────────────────────────────────────────
WEB_PORT = 5000

# ─── Assets à surveiller ─────────────────────────────────────────────────────
STOCKS = [
    "AAPL",   # Apple
    "NVDA",   # Nvidia
    "TSLA",   # Tesla
    "MSFT",   # Microsoft
    "AMZN",   # Amazon
]

CRYPTO = [
    "bitcoin",
    "ethereum",
    "solana",
    "ripple",
]

# ─── Paramètres des indicateurs ───────────────────────────────────────────────
RSI_PERIOD = 14
RSI_OVERSOLD = 30       # signal ACHAT si RSI < 30
RSI_OVERBOUGHT = 70     # signal VENTE si RSI > 70

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

EMA_SHORT = 9
EMA_LONG = 21

# ─── Intervalle de vérification (minutes) ─────────────────────────────────────
CHECK_INTERVAL_MINUTES = 15

# ─── Timeframe Yahoo Finance ──────────────────────────────────────────────────
# "1d" = données journalières (recommandé pour débuter)
# "1h" = données horaires (plus de signaux, plus de bruit)
STOCK_INTERVAL = "1d"
STOCK_PERIOD = "3mo"   # 3 mois d'historique
