import pandas as pd
from dataclasses import dataclass
from config import RSI_OVERSOLD, RSI_OVERBOUGHT
from indicators import add_indicators


@dataclass
class Signal:
    asset: str
    asset_type: str   # "stock" ou "crypto"
    action: str       # "ACHAT" ou "VENTE"
    price: float
    rsi: float
    reasons: list[str]
    strength: int     # nombre de conditions remplies (1, 2 ou 3)


def analyze(asset: str, df: pd.DataFrame, asset_type: str) -> Signal | None:
    df = add_indicators(df)
    if df.empty:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    price = float(last["close"])
    rsi = float(last["rsi"])
    macd = float(last["macd"])
    macd_sig = float(last["macd_signal"])
    prev_macd = float(prev["macd"])
    prev_macd_sig = float(prev["macd_signal"])
    ema_short = float(last["ema_short"])
    ema_long = float(last["ema_long"])

    buy_reasons = []
    sell_reasons = []

    # ── RSI ──────────────────────────────────────────────────────────────────
    if rsi < RSI_OVERSOLD:
        buy_reasons.append(f"RSI survendu ({rsi:.1f} < {RSI_OVERSOLD})")
    elif rsi > RSI_OVERBOUGHT:
        sell_reasons.append(f"RSI suracheté ({rsi:.1f} > {RSI_OVERBOUGHT})")

    # ── MACD crossover ────────────────────────────────────────────────────────
    macd_crossed_up = prev_macd < prev_macd_sig and macd > macd_sig
    macd_crossed_down = prev_macd > prev_macd_sig and macd < macd_sig

    if macd_crossed_up:
        buy_reasons.append("MACD croise à la hausse")
    if macd_crossed_down:
        sell_reasons.append("MACD croise à la baisse")

    # ── EMA crossover ─────────────────────────────────────────────────────────
    prev_ema_short = float(prev["ema_short"])
    prev_ema_long = float(prev["ema_long"])
    ema_crossed_up = prev_ema_short < prev_ema_long and ema_short > ema_long
    ema_crossed_down = prev_ema_short > prev_ema_long and ema_short < ema_long

    if ema_crossed_up:
        buy_reasons.append(f"EMA{9} croise EMA{21} à la hausse")
    if ema_crossed_down:
        sell_reasons.append(f"EMA{9} croise EMA{21} à la baisse")

    # ── Décision : au moins 2 conditions sur 3 ────────────────────────────────
    if len(buy_reasons) >= 2:
        return Signal(asset, asset_type, "ACHAT", price, rsi, buy_reasons, len(buy_reasons))
    if len(sell_reasons) >= 2:
        return Signal(asset, asset_type, "VENTE", price, rsi, sell_reasons, len(sell_reasons))

    return None
