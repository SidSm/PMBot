# Polymarket Account Evaluator

A Python tool to evaluate Polymarket trading accounts based on performance metrics to identify high-quality traders worth copying.

## Features

Evaluates accounts on 9 key criteria:
- ✅ Total PnL: $50K+
- ✅ Win Rate: 55-70%
- ✅ Total Trades: 100-800
- ✅ Active >3 months
- ✅ Specialized niche (>40% concentration)
- ✅ Position sizing consistent (CV < 1.0)
- ✅ Recent performance (last 30 days) still positive
- ✅ No single massive win making up >50% of PnL
- ✅ Trades liquid markets (>70% still active)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py <wallet_address>
```

### Example

```bash
python main.py 0x1234567890abcdef1234567890abcdef12345678
```

## Output

The tool provides a detailed evaluation report:

```
==================================================
POLYMARKET ACCOUNT EVALUATION
==================================================
Address: 0x1234...5678
Evaluated: 2026-02-05 14:30:15 UTC

--------------------------------------------------
METRICS BREAKDOWN
--------------------------------------------------
✅ Total PnL: $52,340.00 (Pass)
✅ Win Rate: 62.5% (Pass)
   └─ Ties/Pushes: 15 trades
✅ Total Trades: 234 (Pass)
✅ Account Age: 127 days (Pass)
✅ Niche Specialization: Politics (65.0%) (Pass)
✅ Position Sizing CV: 0.67 (Pass)
   └─ Mean bet size: $1,245.00
✅ Recent 30d PnL: $3,450.00 (Pass)
✅ No Single Massive Win: Largest = 35.0% (Pass)
❌ Liquid Markets: 45/78 tradeable (Fail)

--------------------------------------------------
OVERALL RESULT: ❌ FAIL (8/9 criteria)
--------------------------------------------------
```

## Exit Codes

- `0`: All criteria passed
- `1`: Some criteria failed
- `2`: API error
- `3`: Unexpected error
- `130`: User interrupted

## Configuration

Edit `config.py` to adjust thresholds and settings:

```python
THRESHOLDS = {
    'min_pnl': 50000,
    'min_win_rate': 55,
    'max_win_rate': 70,
    # ... etc
}
```

## Project Structure

```
PMBot/
├── config.py              # Configuration and thresholds
├── data_fetcher.py        # Polymarket API client
├── metrics_calculator.py  # Evaluation logic
├── evaluator.py          # Main orchestrator
├── main.py               # CLI entry point
├── utils.py              # Helper functions
└── requirements.txt      # Dependencies
```

## API Documentation

Uses official Polymarket APIs:
- Data API: `https://data-api.polymarket.com`
- Gamma API: `https://gamma-api.polymarket.com`

No authentication required for public data.

## License

MIT
