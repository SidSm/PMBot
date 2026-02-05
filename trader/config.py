"""
Configuration for Polymarket Copycat Trading Bot
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
# Only private key needed - py-clob-client generates API credentials automatically
POLYMARKET_PRIVATE_KEY = os.getenv('POLYMARKET_PRIVATE_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Polymarket API Endpoints
POLYMARKET_CLOB_API = "https://clob.polymarket.com"
POLYMARKET_DATA_API = "https://data-api.polymarket.com"
POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"

# WebSocket Configuration
POLYMARKET_WS_URL = "wss://ws-live-data.polymarket.com"
WS_RECONNECT_DELAY = 5  # seconds
WS_PING_INTERVAL = 30  # seconds

# Polling Fallback Configuration
POLLING_INTERVAL = 10  # seconds (if WebSocket fails)
USE_WEBSOCKET = False  # Try WebSocket first

# Target Account Configuration
TARGET_ACCOUNT = os.getenv('TARGET_ACCOUNT', '').lower()
TARGET_INITIAL_CAPITAL = 10000  # Estimate of their starting capital (USD)

# Trading Mode
DRY_RUN = os.getenv('DRY_RUN', 'true').lower() == 'true'
BANKROLL_MODE = os.getenv('BANKROLL_MODE', 'fixed')  # 'fixed' or 'dynamic'

# Bankroll Settings
FIXED_BANKROLL = float(os.getenv('FIXED_BANKROLL', 1000))  # USD
DYNAMIC_BANKROLL_PCT = 100  # % of wallet balance to use in dynamic mode

VERBOSE_VALIDATION=True

# Validation Thresholds
VALIDATION = {
    # 1. Liquidity check
    'min_liquidity_usd': 1000,

    # 2. Market closing time
    'min_hours_until_close': 24,

    # 3. Volume check
    'min_24h_volume_usd': 5000,

    # 4. Spread check
    'max_spread_pct': 5,

    # 9. Trade age limit
    'max_trade_age_seconds': 60,

    # 11. Rate limiting
    'max_trades_per_hour': 10,
    'min_seconds_between_trades': 30,

    # 12. Daily loss limit
    'daily_loss_limit_pct': 5,

    # 13. Total drawdown protection
    'max_drawdown_pct': 15,

    # 14. Minimum edge requirement
    'min_edge_pct': 0,  # Price must be at least 1% better

    # 15. Kelly criterion cap
    'max_kelly_fraction': 0.25,  # Max 25% of calculated Kelly

    # 16. Outcome matching (always enforced)

    # 17. Price sanity check
    'min_price': 0.01,
    'max_price': 0.99,

    # 18. Duplicate detection (always enforced)

    # 19. Account health recheck interval
    'account_health_check_hours': 24,
}

# Position Limits
POSITION_LIMITS = {
    'min_bet_size_usd': 0.001,
    'max_bet_size_usd': 1000,
    'max_bet_pct_portfolio': 10,
    'max_price_movement_pct': 5,
}

# Execution Settings
EXECUTION = {
    'max_retries': 3,
    'total_timeout': 3,  # seconds
    'retry_delay': 0.5,  # seconds between retries
    'order_type': 'FOK',  # Fill-Or-Kill
}

# Telegram Notification Settings
TELEGRAM = {
    'notify_trades': True,
    'notify_rejections': True,
    'notify_errors': True,
    'notify_circuit_breakers': True,
    'notify_daily_summary': True,
}

# Logging
LOG_LEVEL = 'DEBUG'
LOG_TO_FILE = True
LOG_FILE = 'trader/copycat_bot.log'
