from __future__ import annotations

import json
import os
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from tradingview_ta import TA_Handler, Interval


HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "3000"))

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

TOOLS = [
    {
        "name": "analyze_symbol",
        "description": "Get TradingView technical analysis for one symbol and timeframe.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "TradingView symbol, for example BTCUSDT, XAUUSD, or AAPL."},
                "screener": {"type": "string", "default": "crypto", "description": "TradingView screener, for example crypto, forex, or america."},
                "exchange": {"type": "string", "default": "BINANCE", "description": "TradingView exchange, for example BINANCE, OANDA, or NASDAQ."},
                "interval": {"type": "string", "default": "15m", "description": "Timeframe: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w, or 1M."},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "multi_timeframe_analysis",
        "description": "Compare TradingView recommendations across multiple timeframes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "TradingView symbol, for example BTCUSDT."},
                "screener": {"type": "string", "default": "crypto"},
                "exchange": {"type": "string", "default": "BINANCE"},
                "intervals": {"type": "string", "default": "15m,1h,4h,1d", "description": "Comma-separated timeframes."},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "build_tradingview_alert_plan",
        "description": "Draft TradingView alert conditions and a review checklist for a setup.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "setup": {"type": "string", "description": "Trading setup to monitor."},
                "timeframe": {"type": "string", "default": "15m"},
                "risk_style": {"type": "string", "default": "balanced"},
            },
            "required": ["symbol", "setup"],
        },
    },
]


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
        "indicators": {key: indicators.get(key) for key in keys if key in indicators},
    }


def analyze_symbol(symbol: str, screener: str = "crypto", exchange: str = "BINANCE", interval: str = "15m") -> dict[str, Any]:
    analysis = _handler(symbol, screener, exchange, interval).get_analysis()
    return {
        "symbol": symbol.upper(),
        "screener": screener.lower(),
        "exchange": exchange.upper(),
        "interval": interval,
        **_compact_analysis(analysis),
        "disclaimer": "Technical analysis only. This is not financial advice and does not place trades.",
    }


def multi_timeframe_analysis(
    symbol: str,
    screener: str = "crypto",
    exchange: str = "BINANCE",
    intervals: str = "15m,1h,4h,1d",
) -> dict[str, Any]:
    results = []
    for interval in [item.strip() for item in intervals.split(",") if item.strip()]:
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


def build_tradingview_alert_plan(
    symbol: str,
    setup: str,
    timeframe: str = "15m",
    risk_style: str = "balanced",
) -> dict[str, Any]:
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
        "poke_instruction": "Summarize trend, momentum, support/resistance, invalidation, and what would make the setup lower quality. Do not place a trade.",
        "disclaimer": "Technical analysis only. This is not financial advice and does not place trades.",
    }


def _rpc_result(request_id: Any, result: Any) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


def _rpc_error(request_id: Any, code: int, message: str) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


async def mcp_endpoint(request: Request) -> Response:
    payload = await request.json()
    if isinstance(payload, list):
        responses = [await _handle_rpc(item) for item in payload if item.get("id") is not None]
        return JSONResponse([response for response in responses if response is not None])

    response = await _handle_rpc(payload)
    if response is None:
        return Response(status_code=202)
    return response


async def _handle_rpc(payload: dict[str, Any]) -> JSONResponse | None:
    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    if request_id is None:
        return None

    if method == "initialize":
        return _rpc_result(
            request_id,
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "TradingView Chart Analyst", "version": "1.0.0"},
                "instructions": "Use these tools for technical chart analysis only. Never place trades.",
            },
        )

    if method == "tools/list":
        return _rpc_result(request_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            if name == "analyze_symbol":
                result = analyze_symbol(**arguments)
            elif name == "multi_timeframe_analysis":
                result = multi_timeframe_analysis(**arguments)
            elif name == "build_tradingview_alert_plan":
                result = build_tradingview_alert_plan(**arguments)
            else:
                return _rpc_error(request_id, -32601, f"Unknown tool: {name}")
        except Exception as exc:
            return _rpc_result(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})

        return _rpc_result(
            request_id,
            {"content": [{"type": "text", "text": json.dumps(result, indent=2)}], "isError": False},
        )

    return _rpc_error(request_id, -32601, f"Unknown method: {method}")


async def health(_: Request) -> Response:
    return JSONResponse({"ok": True, "endpoint": "/mcp"})


app = Starlette(
    routes=[
        Route("/", health, methods=["GET", "HEAD"]),
        Route("/mcp", mcp_endpoint, methods=["POST"]),
    ]
)


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
