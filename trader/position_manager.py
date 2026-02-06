"""
Position manager for tracking portfolio state
"""

from typing import Dict, List, Optional
from datetime import datetime, timezone
import requests

import trader.config as config
from trader.wallet_tracker import WalletTracker


class Position:
    """Represents an open position"""

    def __init__(self, condition_id: str, asset: str, side: str, size: float, avg_price: float):
        self.condition_id = condition_id
        self.asset = asset
        self.side = side
        self.size = size
        self.avg_price = avg_price
        self.opened_at = datetime.now(timezone.utc)
        self.unrealized_pnl = 0.0

    def __repr__(self):
        return f"Position({self.side} {self.size} @ {self.avg_price})"


class PositionManager:
    """Manages portfolio positions and net worth tracking"""

    def __init__(self, wallet_tracker: Optional[WalletTracker] = None, wallet_address: Optional[str] = None):
        """
        Initialize position manager

        Args:
            wallet_address: Our wallet address (for dynamic bankroll mode)
        """
        self.wallet_address = wallet_address
        self.wallet_tracker = wallet_tracker
        self.positions: Dict[str, Position] = {}  # condition_id -> Position

        # PnL tracking
        self.initial_capital = 0.0
        self.total_realized_pnl = 0.0
        self.total_unrealized_pnl = 0.0

        # Circuit breaker tracking
        self.daily_pnl = 0.0
        self.daily_reset_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        self.peak_net_worth = 0.0
        self.current_drawdown_pct = 0.0

        # Trade tracking
        self.trade_history: List[Dict] = []
        self.last_trade_time = 0

    def initialize(self, initial_capital: float):
        """
        Initialize with starting capital

        Args:
            initial_capital: Starting bankroll (USD)
        """
        self.initial_capital = initial_capital
        self.peak_net_worth = initial_capital
        print(f"✓ Initialized with ${initial_capital:,.2f}")

    def get_net_worth(self) -> float:
        """
        Calculate current net worth

        Returns:
            Total net worth in USD
        """
        if config.BANKROLL_MODE == 'dynamic' and self.wallet_address and hasattr(self, "wallet_tracker"):
            usdc_balance = self.wallet_tracker.get_usdc_balance(self.wallet_address)
            positions = self.wallet_tracker.get_polymarket_positions_value(self.wallet_address)
            return usdc_balance + positions
        else:
            # Fixed bankroll mode
            return self.initial_capital + self.total_realized_pnl + self.total_unrealized_pnl

    def get_available_capital(self) -> float:
        """
        Get available capital for new positions

        Returns:
            Available capital in USD
        """
        net_worth = self.get_net_worth()
        used_capital = sum(pos.size * pos.avg_price for pos in self.positions.values())
        return net_worth - used_capital

    def calculate_position_size(self, their_bet_size: float, their_net_worth: float) -> float:
        """
        Calculate our position size based on their bet as % of net worth

        Args:
            their_bet_size: Their bet size in USD
            their_net_worth: Their estimated net worth in USD

        Returns:
            Our calculated bet size in USD
        """
        our_net_worth = self.get_net_worth()

        if their_net_worth <= 0 or our_net_worth <= 0:
            return 0.0

        # Calculate their bet as % of net worth
        their_bet_pct = (their_bet_size / their_net_worth) * 100

        # Apply Kelly cap
        their_bet_pct = min(their_bet_pct, config.VALIDATION['max_kelly_fraction'] * 100)

        # Calculate our bet size
        our_bet_size = (their_bet_pct / 100) * our_net_worth

        # Apply position limits
        our_bet_size = max(our_bet_size, config.POSITION_LIMITS['min_bet_size_usd'])
        our_bet_size = min(our_bet_size, config.POSITION_LIMITS['max_bet_size_usd'])

        # Check max % of portfolio
        max_bet = (config.POSITION_LIMITS['max_bet_pct_portfolio'] / 100) * our_net_worth
        our_bet_size = min(our_bet_size, max_bet)

        return round(our_bet_size, 2)

    def has_position(self, condition_id: str) -> bool:
        """
        Check if we already have a position in this market

        Args:
            condition_id: Market condition ID

        Returns:
            True if position exists
        """
        return condition_id in self.positions

    def add_position(self, condition_id: str, asset: str, side: str, size: float, price: float):
        """
        Add a new position

        Args:
            condition_id: Market condition ID
            asset: Token ID
            side: BUY or SELL
            size: Position size
            price: Entry price
        """
        if condition_id in self.positions:
            # Update existing position (average price)
            pos = self.positions[condition_id]
            total_cost = (pos.size * pos.avg_price) + (size * price)
            pos.size += size
            pos.avg_price = total_cost / pos.size
        else:
            # New position
            self.positions[condition_id] = Position(condition_id, asset, side, size, price)

        print(f"✓ Position added: {self.positions[condition_id]}")

    def record_trade(self, trade_details: Dict):
        """
        Record a completed trade

        Args:
            trade_details: Trade information
        """
        self.trade_history.append({
            'timestamp': datetime.now(timezone.utc),
            'details': trade_details
        })
        self.last_trade_time = int(datetime.now(timezone.utc).timestamp())

        # Update daily PnL (simplified - actual PnL calculated on close)
        # This is for circuit breaker monitoring
        cost = trade_details.get('size', 0) * trade_details.get('price', 0)
        self.daily_pnl -= cost  # Subtract cost (will add profit on close)

    def update_daily_stats(self):
        """Update daily statistics and reset if new day"""
        now = datetime.now(timezone.utc)

        if now.date() > self.daily_reset_time.date():
            # New day, reset
            self.daily_pnl = 0.0
            self.daily_reset_time = now.replace(hour=0, minute=0, second=0)

    def update_drawdown(self):
        """Update drawdown calculation"""
        net_worth = self.get_net_worth()

        if net_worth > self.peak_net_worth:
            self.peak_net_worth = net_worth
            self.current_drawdown_pct = 0.0
        else:
            self.current_drawdown_pct = ((self.peak_net_worth - net_worth) / self.peak_net_worth) * 100

    def get_trades_last_hour(self) -> int:
        """
        Count trades in last hour

        Returns:
            Number of trades
        """
        now = datetime.now(timezone.utc)
        hour_ago = now.timestamp() - 3600

        count = sum(1 for trade in self.trade_history
                    if trade['timestamp'].timestamp() > hour_ago)
        return count

    def get_portfolio_summary(self) -> Dict:
        """
        Get portfolio summary statistics

        Returns:
            Dictionary with portfolio stats
        """
        return {
            'net_worth': self.get_net_worth(),
            'available_capital': self.get_available_capital(),
            'total_pnl': self.total_realized_pnl + self.total_unrealized_pnl,
            'realized_pnl': self.total_realized_pnl,
            'unrealized_pnl': self.total_unrealized_pnl,
            'open_positions': len(self.positions),
            'daily_pnl': self.daily_pnl,
            'drawdown_pct': self.current_drawdown_pct,
            'total_trades': len(self.trade_history)
        }
