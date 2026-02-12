# CLAUDE.md

Project context for AI-assisted development.

## What is this?

PMBot is a Python toolkit for Polymarket prediction markets. Two modules:

1. **`evaluator/`** — Scores trader accounts against 9 criteria (PnL, win rate, consistency, etc.) to find accounts worth copy-trading. No auth needed, uses public APIs.
2. **`trader/`** — Copycat trading bot that monitors a target account by polling the Data API and mirrors trades. Has a 14-point validation pipeline, risk management with circuit breakers, and Telegram notifications.

## Tech Stack

- Python 3.12
- `py-clob-client` — Polymarket CLOB trading API
- `web3` — Ethereum/blockchain interaction
- `python-telegram-bot` — Notifications
- `python-dotenv` — Environment config

## Key APIs

- Data API: `https://data-api.polymarket.com` (public trade/position data, polling)
- Gamma API: `https://gamma-api.polymarket.com` (market metadata)
- CLOB API: `https://clob.polymarket.com` (order placement, authenticated)

## Running

```bash
# Evaluator (no auth)
python evaluator/main.py <wallet_address>

# Trader (requires .env)
python trader/main.py
```

## Configuration

- Trader config lives in `.env` (see `.env.example`)
- Evaluator thresholds live in `evaluator/config.py`
- **Never commit `.env`** — it contains private keys

## Architecture Notes

- Evaluator pipeline: `main.py` → `AccountEvaluator` → `DataFetcher` → `MetricsCalculator`
- Trader pipeline: `main.py` → `CopycatBot` → `TradeMonitor` → `TradeValidator` → `OrderExecutor`
- Risk management is handled by `RiskManager` (circuit breakers for daily loss and drawdown)
- `PositionManager` tracks portfolio state and calculates net worth from on-chain data
- Trade detection uses polling (CLOB WebSocket can't monitor other users' trades)
- `websocket_monitor.py` is named historically — it's pure polling now

## Conventions

- No type stubs or docstrings unless the logic is genuinely non-obvious
- Config constants go in the respective module's `config.py`
- Keep validation logic in `trade_validator.py`, not scattered across modules
- Exit codes: 0 = success, 1 = criteria failed, 2 = API error, 3 = unexpected error
