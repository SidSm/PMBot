"""
Risk manager for circuit breakers and portfolio protection
"""

import trader.config as config
from trader.position_manager import PositionManager


class CircuitBreakerException(Exception):
    """Raised when circuit breaker is triggered"""
    pass


class RiskManager:
    """Manages risk and circuit breakers"""

    def __init__(self, position_manager: PositionManager):
        """
        Initialize risk manager

        Args:
            position_manager: Position manager instance
        """
        self.position_manager = position_manager
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""

    def check_circuit_breakers(self) -> bool:
        """
        Check all circuit breakers

        Returns:
            True if all clear, False if breaker triggered

        Raises:
            CircuitBreakerException: If circuit breaker triggered
        """
        if self.circuit_breaker_active:
            return False

        # Check daily loss limit
        if not self._check_daily_loss_limit():
            self.trigger_circuit_breaker("Daily loss limit exceeded")
            return False

        # Check drawdown limit
        if not self._check_drawdown_limit():
            self.trigger_circuit_breaker("Maximum drawdown exceeded")
            return False

        return True

    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit breached"""
        self.position_manager.update_daily_stats()

        daily_pnl = self.position_manager.daily_pnl
        net_worth = self.position_manager.get_net_worth()

        if net_worth <= 0:
            return True

        daily_pnl_pct = (daily_pnl / net_worth) * 100
        max_loss_pct = config.VALIDATION['daily_loss_limit_pct']

        return daily_pnl_pct >= -max_loss_pct

    def _check_drawdown_limit(self) -> bool:
        """Check if drawdown limit breached"""
        self.position_manager.update_drawdown()

        drawdown_pct = self.position_manager.current_drawdown_pct
        max_drawdown = config.VALIDATION['max_drawdown_pct']

        return drawdown_pct <= max_drawdown

    def trigger_circuit_breaker(self, reason: str):
        """
        Activate circuit breaker

        Args:
            reason: Reason for activation
        """
        self.circuit_breaker_active = True
        self.circuit_breaker_reason = reason
        print(f"\n🚨 CIRCUIT BREAKER ACTIVATED: {reason}")

    def reset_circuit_breaker(self):
        """Reset circuit breaker (manual intervention)"""
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""
        print("✓ Circuit breaker reset")

    def get_risk_stats(self) -> dict:
        """
        Get current risk statistics

        Returns:
            Dictionary with risk metrics
        """
        stats = self.position_manager.get_portfolio_summary()

        return {
            'circuit_breaker_active': self.circuit_breaker_active,
            'circuit_breaker_reason': self.circuit_breaker_reason,
            'daily_loss_pct': (stats['daily_pnl'] / stats['net_worth'] * 100) if stats['net_worth'] > 0 else 0,
            'drawdown_pct': stats['drawdown_pct'],
            'trades_last_hour': self.position_manager.get_trades_last_hour(),
            'available_capital_pct': (stats['available_capital'] / stats['net_worth'] * 100) if stats['net_worth'] > 0 else 0,
        }
