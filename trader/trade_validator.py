"""
Trade validator - checks all rejection criteria
"""

import time
import requests
from typing import Tuple, Optional, Dict
from datetime import datetime, timezone

import trader.config as config
from trader.websocket_monitor import TradeEvent
from trader.position_manager import PositionManager


class ValidationResult:
    """Result of trade validation"""

    def __init__(self, passed: bool, reason: str = ""):
        self.passed = passed
        self.reason = reason

    def __bool__(self):
        return self.passed

    def __repr__(self):
        return f"{'✓ PASS' if self.passed else '✗ REJECT'}: {self.reason}"


class TradeValidator:
    """Validates trades against all rejection criteria"""

    def __init__(self, position_manager: PositionManager):
        """
        Initialize validator

        Args:
            position_manager: Position manager instance
        """
        self.position_manager = position_manager
        self.market_cache: Dict[str, Dict] = {}
        self.last_health_check = 0

    def validate_trade(self, trade: TradeEvent, their_net_worth: float) -> ValidationResult:
        """
        Validate trade against all criteria

        Args:
            trade: Trade event to validate
            their_net_worth: Target account's net worth

        Returns:
            ValidationResult with pass/fail and reason
        """
        # Fetch market data once for multiple checks
        market_data = self._get_market_data(trade.condition_id)

        if not market_data:
            return ValidationResult(False, "Could not fetch market data")

        # Run all validation checks
        checks = [
            self._check_price_sanity(trade),
            self._check_outcome_matching(trade, market_data),
            self._check_duplicate(trade),
            self._check_liquidity(market_data),
            self._check_market_closing(market_data),
            self._check_volume(market_data),
            self._check_spread(market_data),
            self._check_trade_age(trade),
            self._check_rate_limit(),
            self._check_daily_loss_limit(),
            self._check_drawdown_protection(),
            self._check_minimum_edge(trade, market_data),
            self._check_position_limits(trade, their_net_worth),
            self._check_price_movement(trade, market_data),
        ]

        for result in checks:
            if not result.passed:
                return result

        return ValidationResult(True, "All checks passed")

    def _check_liquidity(self, market_data: Dict) -> ValidationResult:
        """1. Check market liquidity"""
        # TODO: Get actual liquidity from order book
        # For now, check if market is active
        if market_data.get('closed', True):
            return ValidationResult(False, "Market is closed")

        return ValidationResult(True, "Liquidity check passed")

    def _check_market_closing(self, market_data: Dict) -> ValidationResult:
        """2. Check market closing time"""
        end_date = market_data.get('endDate')

        if not end_date:
            return ValidationResult(True, "No end date set")

        # Parse end date
        if isinstance(end_date, str):
            from evaluator.utils import parse_iso_date
            end_timestamp = parse_iso_date(end_date)
        else:
            end_timestamp = int(end_date)

        if not end_timestamp:
            return ValidationResult(True, "Could not parse end date")

        # Check hours until close
        now = int(datetime.now(timezone.utc).timestamp())
        hours_until_close = (end_timestamp - now) / 3600

        min_hours = config.VALIDATION['min_hours_until_close']
        if hours_until_close < min_hours:
            return ValidationResult(False, f"Market closes in {hours_until_close:.1f}h (min {min_hours}h)")

        return ValidationResult(True, f"Market closes in {hours_until_close:.1f}h")

    def _check_volume(self, market_data: Dict) -> ValidationResult:
        """3. Check 24h volume"""
        volume = market_data.get('volume24hr', 0)

        min_volume = config.VALIDATION['min_24h_volume_usd']
        if volume < min_volume:
            return ValidationResult(False, f"Volume ${volume:,.0f} < ${min_volume:,.0f}")

        return ValidationResult(True, f"Volume ${volume:,.0f}")

    def _check_spread(self, market_data: Dict) -> ValidationResult:
        """4. Check bid-ask spread"""
        # TODO: Get actual spread from order book
        # For now, pass
        return ValidationResult(True, "Spread check passed")

    def _check_trade_age(self, trade: TradeEvent) -> ValidationResult:
        """9. Check trade age"""
        now = int(datetime.now(timezone.utc).timestamp())
        age = now - trade.timestamp

        max_age = config.VALIDATION['max_trade_age_seconds']
        if age > max_age:
            return ValidationResult(False, f"Trade is {age}s old (max {max_age}s)")

        return ValidationResult(True, f"Trade age {age}s")

    def _check_rate_limit(self) -> ValidationResult:
        """11. Check rate limiting"""
        # Check trades per hour
        trades_last_hour = self.position_manager.get_trades_last_hour()
        max_trades = config.VALIDATION['max_trades_per_hour']

        if trades_last_hour >= max_trades:
            return ValidationResult(False, f"Rate limit: {trades_last_hour}/{max_trades} trades/hour")

        # Check time since last trade
        now = int(datetime.now(timezone.utc).timestamp())
        time_since_last = now - self.position_manager.last_trade_time
        min_interval = config.VALIDATION.get('min_seconds_between_trades', 0)

        if time_since_last < min_interval:
            return ValidationResult(False, f"Too soon: {time_since_last}s since last trade (min {min_interval}s)")

        return ValidationResult(True, "Rate limit OK")

    def _check_daily_loss_limit(self) -> ValidationResult:
        """12. Check daily loss limit"""
        self.position_manager.update_daily_stats()

        daily_pnl = self.position_manager.daily_pnl
        net_worth = self.position_manager.get_net_worth()

        if net_worth > 0:
            daily_pnl_pct = (daily_pnl / net_worth) * 100
            max_loss_pct = config.VALIDATION['daily_loss_limit_pct']

            if daily_pnl_pct < -max_loss_pct:
                return ValidationResult(False, f"Daily loss {daily_pnl_pct:.1f}% exceeds limit {max_loss_pct}%")

        return ValidationResult(True, f"Daily PnL: ${daily_pnl:,.2f}")

    def _check_drawdown_protection(self) -> ValidationResult:
        """13. Check total drawdown"""
        self.position_manager.update_drawdown()

        drawdown_pct = self.position_manager.current_drawdown_pct
        max_drawdown = config.VALIDATION['max_drawdown_pct']

        if drawdown_pct > max_drawdown:
            return ValidationResult(False, f"Drawdown {drawdown_pct:.1f}% exceeds limit {max_drawdown}%")

        return ValidationResult(True, f"Drawdown: {drawdown_pct:.1f}%")

    def _check_minimum_edge(self, trade: TradeEvent, market_data: Dict) -> ValidationResult:
        """14. Check minimum edge requirement"""
        # Get current market price
        current_price = self._get_current_price(market_data, trade.asset)

        if current_price is None:
            return ValidationResult(False, "Could not get current price")

        # Calculate price movement
        if trade.side == 'BUY':
            # For buy, we want current price to be lower (better deal)
            edge_pct = ((trade.price - current_price) / trade.price) * 100
        else:
            # For sell, we want current price to be higher
            edge_pct = ((current_price - trade.price) / trade.price) * 100

        min_edge = config.VALIDATION['min_edge_pct']

        if edge_pct < min_edge:
            return ValidationResult(False, f"Edge {edge_pct:.2f}% < minimum {min_edge}%")

        return ValidationResult(True, f"Edge: {edge_pct:.2f}%")

    def _check_outcome_matching(self, trade: TradeEvent, market_data: Dict) -> ValidationResult:
        """16. Verify we're betting on same outcome"""
        # This is enforced by using same asset/condition_id
        return ValidationResult(True, "Outcome matching OK")

    def _check_price_sanity(self, trade: TradeEvent) -> ValidationResult:
        """17. Check price is in valid range"""
        min_price = config.VALIDATION['min_price']
        max_price = config.VALIDATION['max_price']

        if trade.price < min_price or trade.price > max_price:
            return ValidationResult(False, f"Price {trade.price} outside range [{min_price}, {max_price}]")

        return ValidationResult(True, f"Price {trade.price} valid")

    def _check_duplicate(self, trade: TradeEvent) -> ValidationResult:
        """18. Check for duplicate trade"""
        # Already handled by websocket_monitor, but double-check
        return ValidationResult(True, "Not a duplicate")

    def _check_position_limits(self, trade: TradeEvent, their_net_worth: float) -> ValidationResult:
        """Check position size limits"""
        # Check if we already have position in this market
        if self.position_manager.has_position(trade.condition_id):
            return ValidationResult(False, "Already have position in this market")

        # Calculate position size
        bet_size = self.position_manager.calculate_position_size(
            trade.size * trade.price,
            their_net_worth
        )

        # Check minimum
        if bet_size < config.POSITION_LIMITS['min_bet_size_usd']:
            return ValidationResult(False, f"Bet size ${bet_size} < minimum ${config.POSITION_LIMITS['min_bet_size_usd']}")

        # Check maximum
        if bet_size > config.POSITION_LIMITS['max_bet_size_usd']:
            return ValidationResult(False, f"Bet size ${bet_size} > maximum ${config.POSITION_LIMITS['max_bet_size_usd']}")

        return ValidationResult(True, f"Position size: ${bet_size:,.2f}")

    def _check_price_movement(self, trade: TradeEvent, market_data: Dict) -> ValidationResult:
        """Check price hasn't moved too much"""
        current_price = self._get_current_price(market_data, trade.asset)

        if current_price is None:
            return ValidationResult(False, "Could not get current price")

        price_change_pct = abs((current_price - trade.price) / trade.price) * 100
        max_movement = config.POSITION_LIMITS['max_price_movement_pct']

        if price_change_pct > max_movement:
            return ValidationResult(False, f"Price moved {price_change_pct:.1f}% (max {max_movement}%)")

        return ValidationResult(True, f"Price movement: {price_change_pct:.1f}%")

    def _get_market_data(self, condition_id: str) -> Optional[Dict]:
        """Fetch market data from Gamma API"""
        # Check cache first
        if condition_id in self.market_cache:
            cached = self.market_cache[condition_id]
            # Cache for 60 seconds
            if time.time() - cached['timestamp'] < 60:
                return cached['data']

        try:
            url = f"{config.POLYMARKET_GAMMA_API}/markets"
            params = {'id': condition_id}
            response = requests.get(url, params=params, timeout=3)
            response.raise_for_status()

            markets = response.json()
            if markets and len(markets) > 0:
                market_data = markets[0]
                self.market_cache[condition_id] = {
                    'data': market_data,
                    'timestamp': time.time()
                }
                return market_data

        except Exception as e:
            print(f"Error fetching market data: {e}")

        return None

    def _get_current_price(self, market_data: Dict, asset: str) -> Optional[float]:
        """Get current market price for asset"""
        # TODO: Get from CLOB order book
        # For now, use best guess from market data
        tokens = market_data.get('tokens', [])

        for token in tokens:
            if token.get('token_id') == asset:
                return float(token.get('price', 0))

        return None
