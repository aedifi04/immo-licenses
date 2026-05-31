import yfinance as yf
import requests
import pandas as pd
from config import STOCK_INTERVAL, STOCK_PERIOD


def fetch_stock(ticker: str) -> pd.DataFrame | None:
    try:
        df = yf.download(ticker, period=STOCK_PERIOD, interval=STOCK_INTERVAL, progress=False, auto_adjust=True)
        if df.empty or len(df) < 30:
            return None
        df = df[["Close", "Volume"]].copy()
        df.columns = ["close", "volume"]
        df.dropna(inplace=True)
        return df
    except Exception as e:
        print(f"[stock] Erreur {ticker}: {e}")
        return None


def fetch_crypto(coin_id: str, days: int = 90) -> pd.DataFrame | None:
    """Récupère l'historique OHLCV depuis CoinGecko (API publique, sans clé)."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "eur", "days": days, "interval": "daily"}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        prices = data.get("prices", [])
        volumes = data.get("total_volumes", [])
        if len(prices) < 30:
            return None
        df = pd.DataFrame(prices, columns=["ts", "close"])
        df["volume"] = [v[1] for v in volumes]
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        df.set_index("ts", inplace=True)
        return df
    except Exception as e:
        print(f"[crypto] Erreur {coin_id}: {e}")
        return None
