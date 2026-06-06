# TradingView Chart Analyst MCP

Public MCP server for a Poke recipe that provides TradingView technical-analysis tools.

## Tools

- `analyze_symbol`: single-symbol technical analysis
- `multi_timeframe_analysis`: compare multiple timeframes
- `build_tradingview_alert_plan`: draft TradingView alert conditions and review checklist

## Local Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
HOST=127.0.0.1 PORT=3000 .venv/bin/python server.py
```

MCP endpoint:

```text
http://127.0.0.1:3000/mcp
```

## Render Deploy

Push this folder to GitHub, then create a Render Blueprint from the repo.

The public MCP endpoint will be:

```text
https://YOUR-RENDER-SERVICE.onrender.com/mcp
```

After deploy, add that URL to Poke:

```bash
npx poke@latest mcp add https://YOUR-RENDER-SERVICE.onrender.com/mcp -n "TradingView Chart Analyst"
```

Then create/manage the recipe in Poke Kitchen and select that integration.

## Notes

This server provides technical analysis only. It does not place trades.
