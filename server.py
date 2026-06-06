from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from tradingview_ta import TA_Handler, Interval


HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "3000"))

mcp = FastMCP(
    "TradingView Chart Analyst",
    host=HOST,
    port=PORT,
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
)


INTERVALS = {
    "1m": Interval.INTERVAL_1_MINUTE,
    "5m": Interval.INTERVAL_5_MINUTES,
    "15m": Interval.INTERVAL_15_MINUTES,
    "30m": Interval.INTERVAL_30_MINUTES,
    "1h": Interval.INTERVAL_1_HOUR,
    "2h": Interval.INTERVAL_2_HOURS,
    "4h": Interval.INTERVAL_4_HOURS,
    "1d": Interval.INTERVAL_1_DAY,
    "1w": Interval.INTERVAL_1_WEEK,
    "1M": Interval.INTERVAL_1_MONTH,
}


def _handler(symbol: str, screener: str, exchange: str, interval: str) -> TA_Handler:
    normalized_interval = INTERVALS.get(interval)
    if not normalized_interval:
        raise ValueError(f"Unsupported interval '{interval}'. Use one of: {', '.join(INTERVALS)}")

    return TA_Handler(
        symbol=symbol.upper(),
        screener=screener.lower(),
        exchange=exchange.upper(),
        interval=normalized_interval,
    )


def _compact_analysis(analysis: Any) -> dict[str, Any]:
    indicators = analysis.indicators or {}
    summary = analysis.summary or {}
    oscillators = analysis.oscillators or {}
    moving_averages = analysis.moving_averages or {}

    keys = [
        "close",
        "open",
        "high",
        "low",
        "volume",
        "RSI",
        "MACD.macd",
        "MACD.signal",
        "ADX",
        "EMA10",
        "EMA20",
        "EMA50",
        "EMA100",
        "EMA200",
        "SMA20",
        "SMA50",
        "SMA200",
        "VWMA",
        "Recommend.All",
        "Recommend.MA",
        "Recommend.Other",
    ]
    selected_indicators = {key: indicators.get(key) for key in keys if key in indicators}

    return {
        "summary": summary,
        "oscillators": {
            "recommendation": oscillators.get("RECOMMENDATION"),
            "buy": oscillators.get("BUY"),
            "neutral": oscillators.get("NEUTRAL"),
            "sell": oscillators.get("SELL"),
        },
        "moving_averages": {
            "recommendation": moving_averages.get("RECOMMENDATION"),
            "buy": moving_averages.get("BUY"),
            "neutral": moving_averages.get("NEUTRAL"),
            "sell": moving_averages.get("SELL"),
        },
        "indicators": selected_indicators,
    }


@mcp.tool()
def analyze_symbol(
    symbol: str,
    screener: str = "crypto",
    exchange: str = "BINANCE",
    interval: str = "15m",
) -> dict[str, Any]:
    """Get TradingView technical analysis for one symbol/timeframe.

    Common examples:
    - BTCUSDT with screener=crypto, exchange=BINANCE
    - XAUUSD with screener=forex, exchange=OANDA
    - AAPL with screener=america, exchange=NASDAQ
    """

    analysis = _handler(symbol, screener, exchange, interval).get_analysis()
    return {
        "symbol": symbol.upper(),
        "screener": screener.lower(),
        "exchange": exchange.upper(),
        "interval": interval,
        **_compact_analysis(analysis),
        "disclaimer": "Technical analysis only. This is not financial advice and does not place trades.",
    }


@mcp.tool()
def multi_timeframe_analysis(
    symbol: str,
    screener: str = "crypto",
    exchange: str = "BINANCE",
    intervals: str = "15m,1h,4h,1d",
) -> dict[str, Any]:
    """Compare TradingView recommendations across multiple timeframes."""

    interval_list = [item.strip() for item in intervals.split(",") if item.strip()]
    results = []
    for interval in interval_list:
        analysis = _handler(symbol, screener, exchange, interval).get_analysis()
        compact = _compact_analysis(analysis)
        results.append(
            {
                "interval": interval,
                "summary": compact["summary"],
                "oscillators": compact["oscillators"],
                "moving_averages": compact["moving_averages"],
                "key_indicators": compact["indicators"],
            }
        )

    return {
        "symbol": symbol.upper(),
        "screener": screener.lower(),
        "exchange": exchange.upper(),
        "timeframes": results,
        "how_to_use": "Look for alignment across higher and lower timeframes. Treat disagreement as chop/risk, not as a forced signal.",
        "disclaimer": "Technical analysis only. This is not financial advice and does not place trades.",
    }


@mcp.tool()
def build_tradingview_alert_plan(
    symbol: str,
    setup: str,
    timeframe: str = "15m",
    risk_style: str = "balanced",
) -> dict[str, Any]:
    """Draft TradingView alert conditions and a review checklist for a setup."""

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "risk_style": risk_style,
        "setup": setup,
        "alert_plan": [
            "Trend check: alert when price crosses the selected EMA/VWAP level in the setup direction.",
            "Momentum check: alert when RSI or MACD confirms, rather than on price alone.",
            "Invalidation check: alert if price closes beyond the setup invalidation level.",
            "Review check: ask Poke to re-run multi_timeframe_analysis before acting.",
        ],
        "poke_instruction": (
            "When this alert fires, summarize trend, momentum, support/resistance, invalidation, "
            "and what would make the setup lower quality. Do not place a trade."
        ),
        "disclaimer": "Technical analysis only. This is not financial advice and does not place trades.",
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
