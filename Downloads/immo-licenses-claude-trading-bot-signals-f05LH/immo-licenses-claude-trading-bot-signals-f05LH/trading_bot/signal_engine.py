import pandas as pd
from dataclasses import dataclass
from typing import Any
from config import RSI_OVERSOLD, RSI_OVERBOUGHT, MOMENTUM_PERIODS, MOMENTUM_THRESHOLD
from indicators import add_indicators


@dataclass
class Signal:
    asset: str
    asset_type: str
    action: str        # "ACHAT" | "VENTE"
    price: float
    rsi: float
    momentum: float    # % variation sur MOMENTUM_PERIODS bougies
    reasons: list[str]
    strength: int


def analyze(asset: str, df: pd.DataFrame, asset_type: str) -> Signal | None:
    df = add_indicators(df)
    if len(df) < MOMENTUM_PERIODS + 2:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    price    = float(last["close"])
    rsi      = float(last["rsi"])
    momentum = (price - float(df.iloc[-(MOMENTUM_PERIODS + 1)]["close"])) / float(df.iloc[-(MOMENTUM_PERIODS + 1)]["close"]) * 100

    buy_reasons: list[str] = []
    sell_reasons: list[str] = []

    # ── 1. Momentum de prix ───────────────────────────────────────────────────
    if momentum > MOMENTUM_THRESHOLD:
        buy_reasons.append(f"Hausse de +{momentum:.1f}% sur {MOMENTUM_PERIODS}h")
    elif momentum < -MOMENTUM_THRESHOLD:
        sell_reasons.append(f"Baisse de {momentum:.1f}% sur {MOMENTUM_PERIODS}h — risque de continuer")

    # ── 2. RSI ────────────────────────────────────────────────────────────────
    if rsi < RSI_OVERSOLD:
        buy_reasons.append(f"RSI survendu ({rsi:.1f}) — rebond probable")
    elif rsi > RSI_OVERBOUGHT:
        sell_reasons.append(f"RSI suracheté ({rsi:.1f}) — correction probable")

    # ── 3. MACD crossover ────────────────────────────────────────────────────
    if float(prev["macd"]) < float(prev["macd_signal"]) and float(last["macd"]) > float(last["macd_signal"]):
        buy_reasons.append("MACD croise à la hausse")
    elif float(prev["macd"]) > float(prev["macd_signal"]) and float(last["macd"]) < float(last["macd_signal"]):
        sell_reasons.append("MACD croise à la baisse")

    # ── 4. EMA crossover ─────────────────────────────────────────────────────
    if float(prev["ema_short"]) < float(prev["ema_long"]) and float(last["ema_short"]) > float(last["ema_long"]):
        buy_reasons.append(f"EMA{9} repasse au-dessus EMA{21}")
    elif float(prev["ema_short"]) > float(prev["ema_long"]) and float(last["ema_short"]) < float(last["ema_long"]):
        sell_reasons.append(f"EMA{9} repasse sous EMA{21}")

    if len(buy_reasons) >= 2:
        return Signal(asset, asset_type, "ACHAT", price, rsi, momentum, buy_reasons, len(buy_reasons))
    if len(sell_reasons) >= 2:
        return Signal(asset, asset_type, "VENTE", price, rsi, momentum, sell_reasons, len(sell_reasons))
    return None


def get_chart_signals(df: pd.DataFrame, asset: str, asset_type: str) -> list[dict[str, Any]]:
    """Repère les signaux historiques sur les données passées pour l'affichage du graphique."""
    markers: list[dict[str, Any]] = []
    last_action: str | None = None
    last_idx = -6

    for i in range(30, len(df)):
        window = df.iloc[:i + 1].copy()
        sig = analyze(asset, window, asset_type)
        if sig and (sig.action != last_action or i - last_idx > 5):
            ts = int(df.index[i].timestamp())
            is_buy = sig.action == "ACHAT"
            markers.append({
                "time": ts,
                "position": "belowBar" if is_buy else "aboveBar",
                "color": "#3fb950" if is_buy else "#f85149",
                "shape": "arrowUp" if is_buy else "arrowDown",
                "text": sig.action,
            })
            last_action = sig.action
            last_idx = i

    return markers
