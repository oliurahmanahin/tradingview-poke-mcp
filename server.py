from __future__ import annotations

import math
import os
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP


HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "3000"))

mcp = FastMCP(
    "ES and GC Futures Chart Analyst",
    host=HOST,
    port=PORT,
    sse_path="/sse",
    message_path="/messages/",
)

FUTURES = {
    "ES": {
        "ticker": "ES=F",
        "name": "E-mini S&P 500 futures",
        "market": "CME equity index futures",
    },
    "GC": {
        "ticker": "GC=F",
        "name": "Gold futures",
        "market": "COMEX metals futures",
    },
}

INTERVAL_CONFIG = {
    "5m": {"interval": "5m", "range": "5d"},
    "15m": {"interval": "15m", "range": "5d"},
    "1h": {"interval": "60m", "range": "1mo"},
    "1d": {"interval": "1d", "range": "6mo"},
}


def _contract(value: str) -> dict[str, str]:
    key = value.upper().replace("=F", "").replace("1!", "")
    if key not in FUTURES:
        raise ValueError("Only ES and GC futures are supported. Use contract='ES' or contract='GC'.")
    return {"key": key, **FUTURES[key]}


def _fetch_chart(contract: str, interval: str) -> dict[str, Any]:
    info = _contract(contract)
    config = INTERVAL_CONFIG.get(interval)
    if not config:
        raise ValueError(f"Unsupported interval '{interval}'. Use one of: {', '.join(INTERVAL_CONFIG)}")

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{info['ticker'].replace('=', '%3D')}"
    response = requests.get(
        url,
        params={"range": config["range"], "interval": config["interval"]},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        error = payload.get("chart", {}).get("error")
        raise ValueError(f"Could not fetch futures data: {error}")

    quote = result["indicators"]["quote"][0]
    rows = []
    for ts, open_, high, low, close, volume in zip(
        result["timestamp"],
        quote["open"],
        quote["high"],
        quote["low"],
        quote["close"],
        quote["volume"],
    ):
        if close is None or high is None or low is None:
            continue
        rows.append(
            {
                "timestamp": ts,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
    if len(rows) < 30:
        raise ValueError(f"Not enough {interval} data for {info['key']}.")

    return {"contract": info, "interval": interval, "rows": rows}


def _ema(values: list[float], length: int) -> float:
    alpha = 2 / (length + 1)
    ema = values[0]
    for value in values[1:]:
        ema = alpha * value + (1 - alpha) * ema
    return ema


def _rsi(values: list[float], length: int = 14) -> float:
    if len(values) <= length:
        return 50.0
    gains = []
    losses = []
    for previous, current in zip(values[-length - 1 : -1], values[-length:]):
        change = current - previous
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
    average_gain = sum(gains) / length
    average_loss = sum(losses) / length
    if average_loss == 0:
        return 100.0
    rs = average_gain / average_loss
    return 100 - (100 / (1 + rs))


def _analysis_for(contract: str, interval: str) -> dict[str, Any]:
    chart = _fetch_chart(contract, interval)
    rows = chart["rows"]
    closes = [row["close"] for row in rows]
    highs = [row["high"] for row in rows]
    lows = [row["low"] for row in rows]
    last = closes[-1]
    ema20 = _ema(closes[-80:], 20)
    ema50 = _ema(closes[-120:], 50)
    rsi = _rsi(closes)
    prior_high = max(highs[-21:-1])
    prior_low = min(lows[-21:-1])
    range_position = (last - prior_low) / (prior_high - prior_low) if prior_high != prior_low else 0.5

    trend = "bullish" if last > ema20 > ema50 else "bearish" if last < ema20 < ema50 else "mixed"
    momentum = "strong" if rsi >= 60 else "weak" if rsi <= 40 else "neutral"
    bias_score = (1 if trend == "bullish" else -1 if trend == "bearish" else 0) + (
        1 if momentum == "strong" else -1 if momentum == "weak" else 0
    )
    recommendation = "BUY" if bias_score >= 2 else "SELL" if bias_score <= -2 else "NEUTRAL"

    return {
        "interval": interval,
        "last": round(last, 2),
        "trend": trend,
        "momentum": momentum,
        "recommendation": recommendation,
        "rsi": round(rsi, 1),
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "recent_high": round(prior_high, 2),
        "recent_low": round(prior_low, 2),
        "range_position": round(range_position, 2),
    }


@mcp.tool()
def analyze_symbol(symbol: str = "ES", interval: str = "15m") -> dict[str, Any]:
    """Analyze only ES or GC futures for one timeframe."""

    info = _contract(symbol)
    analysis = _analysis_for(info["key"], interval)
    return {
        "contract": info["key"],
        "name": info["name"],
        "market": info["market"],
        **analysis,
        "disclaimer": "Futures chart analysis only. This is not financial advice and does not place trades.",
    }


@mcp.tool()
def multi_timeframe_analysis(symbol: str = "ES", intervals: str = "5m,15m,1h") -> dict[str, Any]:
    """Compare ES or GC futures across multiple timeframes."""

    info = _contract(symbol)
    interval_list = [item.strip() for item in intervals.split(",") if item.strip()]
    timeframes = [_analysis_for(info["key"], interval) for interval in interval_list]
    recommendations = {item["recommendation"] for item in timeframes}
    trends = {item["trend"] for item in timeframes}
    agreement = "aligned" if len(recommendations) == 1 and len(trends) == 1 else "mixed"

    return {
        "contract": info["key"],
        "name": info["name"],
        "market": info["market"],
        "timeframes": timeframes,
        "agreement": agreement,
        "how_to_use": "Use 15m for opening range structure, 5m for break-and-retest confirmation, and 1h for higher-timeframe context.",
        "disclaimer": "Futures chart analysis only. This is not financial advice and does not place trades.",
    }


@mcp.tool()
def build_tradingview_alert_plan(symbol: str = "ES", setup: str = "15m ORB break and 5m retest", timeframe: str = "5m") -> dict[str, Any]:
    """Draft an ES/GC futures alert plan for the ORB-style setup."""

    info = _contract(symbol)
    return {
        "contract": info["key"],
        "name": info["name"],
        "setup": setup,
        "timeframe": timeframe,
        "alert_plan": [
            "Mark the 15-minute RTH opening range high and low.",
            "Wait for a 5-minute candle close outside the range.",
            "Wait for a pullback/retest of the broken range level.",
            "Require rejection from the retest level before considering direction.",
            "Invalidate if price closes back inside the opening range after the retest.",
        ],
        "poke_instruction": "Summarize ORB direction, retest quality, momentum, invalidation, and risk. Do not place a trade.",
        "disclaimer": "Futures chart analysis only. This is not financial advice and does not place trades.",
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
