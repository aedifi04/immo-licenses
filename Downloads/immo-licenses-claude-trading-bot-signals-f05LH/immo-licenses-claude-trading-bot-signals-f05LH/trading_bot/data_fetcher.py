import yfinance as yf
import requests
import pandas as pd
from config import STOCK_INTERVAL, STOCK_PERIOD, CRYPTO_BINANCE, CRYPTO_INTERVAL, CRYPTO_LIMIT

BINANCE = "https://api.binance.com/api/v3"


def fetch_stock(ticker: str) -> pd.DataFrame | None:
    try:
        df = yf.download(ticker, period=STOCK_PERIOD, interval=STOCK_INTERVAL,
                         progress=False, auto_adjust=True)
        if df.empty or len(df) < 30:
            return None
        df = df[["Close", "Volume"]].copy()
        df.columns = ["close", "volume"]
        df.dropna(inplace=True)
        return df
    except Exception as e:
        print(f"[stock] Erreur {ticker}: {e}")
        return None


def fetch_crypto(coin_id: str) -> pd.DataFrame | None:
    symbol = CRYPTO_BINANCE.get(coin_id)
    if not symbol:
        return None
    try:
        r = requests.get(f"{BINANCE}/klines",
                         params={"symbol": symbol, "interval": CRYPTO_INTERVAL,
                                 "limit": CRYPTO_LIMIT},
                         timeout=10)
        r.raise_for_status()
        cols = ["ts","open","high","low","close","volume",
                "ct","qv","n","tbb","tbq","ignore"]
        df = pd.DataFrame(r.json(), columns=cols)
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        df.set_index("ts", inplace=True)
        return df[["open","high","low","close","volume"]].astype(float)
    except Exception as e:
        print(f"[crypto] Erreur {coin_id}: {e}")
        return None


def fetch_live_price_crypto(coin_id: str) -> tuple[float, float] | None:
    """Retourne (prix, variation_24h_pct)."""
    symbol = CRYPTO_BINANCE.get(coin_id)
    if not symbol:
        return None
    try:
        r = requests.get(f"{BINANCE}/ticker/24hr",
                         params={"symbol": symbol}, timeout=5)
        r.raise_for_status()
        d = r.json()
        return float(d["lastPrice"]), float(d["priceChangePercent"])
    except Exception:
        return None


def fetch_live_price_stock(ticker: str) -> tuple[float, float] | None:
    """Retourne (prix, variation_24h_pct)."""
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = float(info.last_price)
        prev  = float(info.previous_close)
        pct   = (price - prev) / prev * 100 if prev else 0.0
        return price, pct
    except Exception:
        return None
