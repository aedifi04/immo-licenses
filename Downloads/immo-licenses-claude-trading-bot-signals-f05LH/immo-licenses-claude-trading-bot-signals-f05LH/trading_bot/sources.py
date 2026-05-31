"""
Sources de données externes gratuites — aucune clé API requise.
Résultats mis en cache 30 min pour éviter le rate limiting.
"""
import time
import requests
import feedparser
from typing import Any

_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 1800   # 30 minutes
_HEADERS = {"User-Agent": "Mozilla/5.0 TradingBot/1.0"}


def _cached(key: str, fn: Any, *args: Any) -> Any:
    now = time.time()
    if key in _cache and now - _cache[key][0] < _CACHE_TTL:
        return _cache[key][1]
    result = fn(*args)
    if result is not None:
        _cache[key] = (now, result)
    return result


# ── Reddit ─────────────────────────────────────────────────────────────────────

def get_reddit_sentiment(query: str) -> dict[str, Any]:
    """Analyse le sentiment des posts Reddit des dernières 24h."""
    def _fetch(q: str) -> dict[str, Any] | None:
        try:
            r = requests.get(
                "https://www.reddit.com/search.json",
                params={"q": q, "sort": "new", "limit": 25, "t": "day"},
                headers=_HEADERS, timeout=10
            )
            if r.status_code != 200:
                return None
            posts = r.json()["data"]["children"]
            positive = sum(1 for p in posts if p["data"]["score"] > 5)
            total = len(posts)
            ratio = positive / total if total else 0.5
            titles = [p["data"]["title"] for p in posts[:4]]
            label = "Bullish 🟢" if ratio > 0.6 else ("Bearish 🔴" if ratio < 0.4 else "Neutre ⚪")
            return {"total": total, "ratio": round(ratio, 2), "titles": titles, "label": label}
        except Exception as e:
            print(f"[reddit] {e}")
            return None

    return _cached(f"reddit_{query}", _fetch, query) or {
        "total": 0, "ratio": 0.5, "titles": [], "label": "N/A"
    }


# ── Fear & Greed Index (crypto) ────────────────────────────────────────────────

def get_fear_greed() -> dict[str, Any]:
    """Fear & Greed Index global crypto (0 = peur extrême, 100 = euphorie)."""
    def _fetch() -> dict[str, Any] | None:
        try:
            r = requests.get("https://api.alternative.me/fng/?limit=1",
                             headers=_HEADERS, timeout=5)
            d = r.json()["data"][0]
            v = int(d["value"])
            color = "#f85149" if v < 25 else "#e3b341" if v < 50 else "#3fb950" if v < 75 else "#00d4aa"
            return {"value": v, "label": d["value_classification"], "color": color}
        except Exception as e:
            print(f"[fear&greed] {e}")
            return None

    return _cached("fear_greed", _fetch) or {"value": 50, "label": "Neutral", "color": "#e3b341"}


# ── Actualités via RSS ─────────────────────────────────────────────────────────

_CRYPTO_RSS: dict[str, str] = {
    "bitcoin":  "https://cointelegraph.com/rss/tag/bitcoin",
    "ethereum": "https://cointelegraph.com/rss/tag/ethereum",
    "solana":   "https://cointelegraph.com/rss/tag/solana",
    "ripple":   "https://cointelegraph.com/rss/tag/xrp",
}

def get_news(ticker: str, is_crypto: bool = False) -> list[str]:
    """Retourne les 6 derniers titres d'actualité pour un actif."""
    def _fetch(t: str, crypto: bool) -> list[str] | None:
        try:
            if crypto:
                url = _CRYPTO_RSS.get(t.lower(),
                      f"https://cointelegraph.com/rss/tag/{t.lower()}")
            else:
                url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={t}&region=US&lang=en-US"
            feed = feedparser.parse(url)
            return [e.title for e in feed.entries[:6]] or None
        except Exception as e:
            print(f"[news] {e}")
            return None

    return _cached(f"news_{ticker}", _fetch, ticker, is_crypto) or []


# ── Fondamentaux Yahoo Finance (stocks) ───────────────────────────────────────

def get_fundamentals(ticker: str) -> dict[str, Any]:
    """P/E, EPS, Market Cap depuis yfinance."""
    def _fetch(t: str) -> dict[str, Any] | None:
        try:
            import yfinance as yf
            info = yf.Ticker(t).info
            return {
                "pe_ratio":    info.get("trailingPE"),
                "eps":         info.get("trailingEps"),
                "market_cap":  info.get("marketCap"),
                "sector":      info.get("sector", ""),
                "analyst_rec": info.get("recommendationKey", ""),
            }
        except Exception as e:
            print(f"[fundamentals] {e}")
            return None

    return _cached(f"fund_{ticker}", _fetch, ticker) or {}
