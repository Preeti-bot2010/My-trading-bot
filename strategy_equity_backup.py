"""
Implements the scoring-based confluence strategy discussed:
trend + volume + RSI + support/resistance + candlestick + ADX regime filter.

score_symbol() returns a dict:
    {
        "score": int (0-9),
        "grade": "A+" | "B" | "C" | "NONE",
        "direction": "LONG" | "SHORT" | None,
        "entry": float, "stop_loss": float, "target": float,
        "reasons": [list of which conditions fired]
    }

This is a STARTING POINT, not a guaranteed-profitable system (no such thing
exists - see earlier conversation). Tune thresholds using the backtester
before trusting it with even paper money.
"""
import pandas as pd
import ta

import config


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema20"] = ta.trend.ema_indicator(df["close"], window=20)
    df["ema50"] = ta.trend.ema_indicator(df["close"], window=50)
    df["rsi"] = ta.momentum.rsi(df["close"], window=14)
    df["adx"] = ta.trend.adx(df["high"], df["low"], df["close"], window=14)
    df["vol_avg20"] = df["volume"].rolling(20).mean()
    return df


def score_symbol(df: pd.DataFrame) -> dict:
    df = add_indicators(df)
    if len(df) < 55 or df.iloc[-1][["ema20", "ema50", "rsi", "adx"]].isna().any():
        return {"score": 0, "grade": "NONE", "direction": None}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    score = 0
    reasons = []
    direction = "LONG" if last["ema20"] > last["ema50"] else "SHORT"

    # 1. Trend alignment (2 pts)
    if direction == "LONG" and last["close"] > last["ema20"] > last["ema50"]:
        score += 2
        reasons.append("Trend aligned bullish (price>EMA20>EMA50)")
    elif direction == "SHORT" and last["close"] < last["ema20"] < last["ema50"]:
        score += 2
        reasons.append("Trend aligned bearish (price<EMA20<EMA50)")

    # 2. Volume spike (2 pts)
    if pd.notna(last["vol_avg20"]) and last["volume"] > 1.5 * last["vol_avg20"]:
        score += 2
        reasons.append("Volume spike vs 20-period average")

    # 3. RSI supportive zone (1 pt)
    if direction == "LONG" and 45 <= last["rsi"] <= 65:
        score += 1
        reasons.append("RSI supportive for longs")
    elif direction == "SHORT" and 35 <= last["rsi"] <= 55:
        score += 1
        reasons.append("RSI supportive for shorts")

    # 4. Support/Resistance confluence via recent swing (2 pts)
    lookback = df.iloc[-20:-1]
    if direction == "LONG" and last["close"] > lookback["high"].max():
        score += 2
        reasons.append("Breakout above recent 20-candle high")
    elif direction == "SHORT" and last["close"] < lookback["low"].min():
        score += 2
        reasons.append("Breakdown below recent 20-candle low")

    # 5. Candle confirmation (1 pt) - simple bullish/bearish close vs open
    if direction == "LONG" and last["close"] > last["open"] and prev["close"] > prev["open"]:
        score += 1
        reasons.append("Two consecutive bullish candles")
    elif direction == "SHORT" and last["close"] < last["open"] and prev["close"] < prev["open"]:
        score += 1
        reasons.append("Two consecutive bearish candles")

    # 6. Regime filter - ADX > 25 means trending market (1 pt)
    if last["adx"] > 25:
        score += 1
        reasons.append(f"ADX {last['adx']:.1f} confirms trending regime")

    if score >= 7:
        grade = "A+"
    elif score >= config.MIN_SCORE_FOR_ENTRY:
        grade = "B"
    elif score >= 3:
        grade = "C"
    else:
        grade = "NONE"

    entry = float(last["close"])
    # Stop-loss: last swing low/high (simple, tune this later)
    if direction == "LONG":
        stop_loss = float(lookback["low"].min())
        risk = entry - stop_loss
        target = entry + risk * config.RISK_REWARD_RATIO
    else:
        stop_loss = float(lookback["high"].max())
        risk = stop_loss - entry
        target = entry - risk * config.RISK_REWARD_RATIO

    return {
        "score": score,
        "grade": grade,
        "direction": direction if grade != "NONE" else None,
        "entry": entry,
        "stop_loss": stop_loss,
        "target": target,
        "reasons": reasons,
    }
