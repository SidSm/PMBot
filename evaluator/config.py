"""
Configuration file for Polymarket Account Evaluator
Contains all thresholds, API settings, and constants
"""

# API Base URLs
API_ENDPOINTS = {
    'data_api': 'https://data-api.polymarket.com',
    'gamma_api': 'https://gamma-api.polymarket.com',
}

# Evaluation Thresholds
THRESHOLDS = {
    'min_pnl': 50000,                # Minimum total PnL in USD
    'min_win_rate': 55,              # Minimum win rate percentage
    'max_win_rate': 70,              # Maximum win rate percentage
    'min_trades': 100,               # Minimum number of trades
    'max_trades': 800,               # Maximum number of trades
    'min_age_days': 90,              # Minimum account age (3 months)
    'niche_concentration': 40,       # Minimum % concentration in one category
    'max_cv': 1.0,                   # Maximum coefficient of variation for position sizing
    'max_single_win_pct': 50,        # Maximum % of PnL from single win
    'min_liquid_markets_pct': 70,    # Minimum % of markets that are liquid
}

# Tie/Push Detection
TIE_PUSH_THRESHOLD = 0.01  # Positions with |realizedPnl| < this are ties/pushes

# Recent Performance Window
RECENT_PERFORMANCE_DAYS = 30

# API Request Settings
REQUEST_SETTINGS = {
    'timeout': 3,           # Request timeout in seconds
    'max_retries': 3,       # Maximum number of retries on failure
    'retry_delay': 1,       # Delay between retries in seconds
    'rate_limit_delay': 0.5, # Delay between API calls in seconds
}

# Pagination Settings
PAGINATION = {
    'trades_limit': 100,
    'positions_limit': 50,
    'max_offset': 10000,
}
