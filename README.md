# PMBot

A Python toolkit for [Polymarket](https://polymarket.com) — evaluate trader accounts and automatically copy their trades.

PMBot has two modules:

- **Evaluator** — scores any Polymarket account against 9 performance criteria to decide if they're worth following
- **Trader** — a copycat bot that monitors a target account in real time and mirrors their trades on your behalf

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Evaluator](#evaluator)
  - [Trader](#trader)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Disclaimer](#disclaimer)
- [License](#license)

---

## Features

### Evaluator — 9-Point Account Scoring

| # | Criterion | Threshold |
|---|-----------|-----------|
| 1 | Total PnL | $50K+ |
| 2 | Win Rate | 55–70% |
| 3 | Trade Count | 100–800 |
| 4 | Account Age | 90+ days |
| 5 | Niche Specialization | >40% in one category |
| 6 | Position Sizing Consistency | CV < 1.0 |
| 7 | Recent Performance | Positive PnL (last 30 days) |
| 8 | No Single-Win Dominance | Largest win < 50% of total PnL |
| 9 | Liquid Markets | >70% of positions still tradeable |

### Trader — Copycat Bot

- **Real-time monitoring** via WebSocket (with polling fallback)
- **19-point trade validation** — liquidity, spread, volume, market close time, rate limits, and more
- **Risk management** — daily loss limits, drawdown circuit breakers, Kelly criterion sizing
- **FOK order execution** with automatic retries
- **Dry-run mode** for paper trading
- **Telegram notifications** — trade alerts, rejections, errors, daily summaries
- **Dynamic or fixed bankroll** modes

---

## Requirements

- Python 3.12+
- A Polymarket account (for the trader module)
- A Telegram bot (optional, for notifications)

---

## Installation

```bash
git clone https://github.com/SidSm/PMBot.git
cd PMBot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Usage

### Evaluator

Analyze any public Polymarket account. No authentication needed.

```bash
python evaluator/main.py <wallet_address>
```

**Example output:**

```
==================================================
POLYMARKET ACCOUNT EVALUATION
==================================================
Address: 0x1234...5678
Evaluated: 2026-02-05 14:30:15 UTC

--------------------------------------------------
METRICS BREAKDOWN
--------------------------------------------------
[PASS] Total PnL: $52,340.00
[PASS] Win Rate: 62.5%
       Ties/Pushes: 15 trades
[PASS] Total Trades: 234
[PASS] Account Age: 127 days
[PASS] Niche Specialization: Politics (65.0%)
[PASS] Position Sizing CV: 0.67
       Mean bet size: $1,245.00
[PASS] Recent 30d PnL: $3,450.00
[PASS] No Single Massive Win: Largest = 35.0%
[FAIL] Liquid Markets: 45/78 tradeable

--------------------------------------------------
OVERALL RESULT: FAIL (8/9 criteria)
--------------------------------------------------
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | All criteria passed |
| 1 | Some criteria failed |
| 2 | API error |
| 3 | Unexpected error |
| 130 | User interrupted (Ctrl+C) |

### Trader

1. Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

2. Edit `.env` with your configuration (see [Configuration](#configuration) below).

3. Run the bot:

```bash
# Dry run (paper trading, no real orders)
python trader/main.py

# Live trading — set DRY_RUN=false in .env
python trader/main.py
```

> **Warning:** Live trading uses real funds. Start with `DRY_RUN=true` and review the logs before going live.

---

## Configuration

The trader is configured via `.env`. See `.env.example` for a template.

| Variable | Description | Required |
|----------|-------------|----------|
| `POLYMARKET_PRIVATE_KEY` | Your wallet private key (from MetaMask export) | Yes |
| `POLYMARKET_FUNDER` | Your Polymarket proxy wallet address | Yes |
| `TARGET_ACCOUNT` | Wallet address of the trader to copy | Yes |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications | No |
| `TELEGRAM_CHAT_ID` | Telegram chat ID for notifications | No |
| `DRY_RUN` | `true` for paper trading, `false` for live | Yes |
| `BANKROLL_MODE` | `fixed` or `dynamic` (uses wallet balance) | Yes |
| `FIXED_BANKROLL` | Starting capital in USD (used when mode is `fixed`) | When fixed |

Evaluator thresholds can be adjusted in `evaluator/config.py`.

---

## Project Structure

```
PMBot/
├── evaluator/
│   ├── main.py                # CLI entry point
│   ├── evaluator.py           # Orchestrator
│   ├── data_fetcher.py        # Polymarket API client
│   ├── metrics_calculator.py  # 9 evaluation criteria
│   ├── config.py              # Thresholds & API endpoints
│   └── utils.py               # Helpers
│
├── trader/
│   ├── main.py                # Bot entry point
│   ├── copycat_bot.py         # Main orchestrator
│   ├── websocket_monitor.py   # Real-time trade detection
│   ├── order_executor.py      # CLOB order placement
│   ├── position_manager.py    # Portfolio tracking
│   ├── trade_validator.py     # 19-point validation
│   ├── risk_manager.py        # Circuit breakers & limits
│   ├── wallet_tracker.py      # On-chain balance queries
│   ├── telegram_notifier.py   # Notifications
│   ├── setup_allowances.py    # Token approval setup
│   ├── check_address.py       # Address utilities
│   └── config.py              # Environment-based settings
│
├── .env.example               # Configuration template
├── requirements.txt           # Python dependencies
└── README.md
```

---

## Disclaimer

This software is provided for educational and research purposes. Trading on prediction markets carries financial risk. The authors are not responsible for any losses incurred through the use of this tool. Always do your own research and never risk more than you can afford to lose.

---

## License

MIT License

Copyright (c) 2025 Ondřej Smolík (SidSm)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
