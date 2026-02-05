"""
Main copycat trading bot orchestrator
"""

import sys
import signal
from typing import Optional
import requests

import trader.config as config
from trader.websocket_monitor import TradeMonitor, TradeEvent
from trader.position_manager import PositionManager
from trader.trade_validator import TradeValidator
from trader.order_executor import OrderExecutor
from trader.risk_manager import RiskManager, CircuitBreakerException
from trader.telegram_notifier import TelegramNotifier


class CopycatBot:
    """Main copycat trading bot"""

    def __init__(self, target_account: str, initial_capital: float):
        """
        Initialize copycat bot

        Args:
            target_account: Ethereum address to copy
            initial_capital: Starting bankroll (USD)
        """
        self.target_account = target_account.lower()
        self.initial_capital = initial_capital
        self.running = False

        # Initialize components
        print("\n" + "="*60)
        print("POLYMARKET COPYCAT TRADING BOT")
        print("="*60)
        print(f"Mode: {'🧪 DRY RUN' if config.DRY_RUN else '✅ LIVE TRADING'}")
        print(f"Target: {self.target_account}")
        print(f"Bankroll: ${initial_capital:,.2f} ({config.BANKROLL_MODE})")
        print("="*60 + "\n")

        print("Initializing components...")

        self.position_manager = PositionManager()
        self.position_manager.initialize(initial_capital)

        self.validator = TradeValidator(self.position_manager)
        self.executor = OrderExecutor(dry_run=config.DRY_RUN)
        self.risk_manager = RiskManager(self.position_manager)
        self.notifier = TelegramNotifier()

        self.monitor = TradeMonitor(
            target_account=self.target_account,
            on_trade_callback=self.on_trade_detected
        )

        # Calculate target's net worth
        self.target_net_worth = self._estimate_target_net_worth()

        print(f"✓ All components initialized")
        print(f"✓ Estimated target net worth: ${self.target_net_worth:,.2f}\n")

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _estimate_target_net_worth(self) -> float:
        """
        Estimate target account's current net worth

        Returns:
            Estimated net worth in USD
        """
        try:
            # Fetch their current positions
            url = f"{config.POLYMARKET_DATA_API}/positions"
            params = {'user': self.target_account, 'limit': 100}
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()

            positions = response.json()

            # Calculate total current value
            total_value = sum(float(pos.get('currentValue', 0)) for pos in positions)

            # Add closed PnL
            url = f"{config.POLYMARKET_DATA_API}/closed-positions"
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()

            closed_positions = response.json()
            realized_pnl = sum(float(pos.get('realizedPnl', 0)) for pos in closed_positions)

            # Estimate: current value of positions + realized PnL + base capital
            estimated_net_worth = total_value + realized_pnl + config.TARGET_INITIAL_CAPITAL

            return max(estimated_net_worth, config.TARGET_INITIAL_CAPITAL)

        except Exception as e:
            print(f"⚠️  Could not estimate target net worth: {e}")
            print(f"Using default: ${config.TARGET_INITIAL_CAPITAL:,.2f}")
            return config.TARGET_INITIAL_CAPITAL

    def start(self):
        """Start the bot"""
        self.running = True

        # Send startup notification
        self.notifier.notify_bot_started(
            target_account=self.target_account,
            config_summary={
                'bankroll': self.initial_capital,
                'mode': config.BANKROLL_MODE
            }
        )

        print("🚀 Bot started! Monitoring for trades...\n")

        try:
            # Start monitoring
            self.monitor.start()

            # Keep main thread alive
            while self.running:
                import time
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n⚠️  Shutdown requested")
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            self.notifier.notify_error(str(e))
        finally:
            self.stop()

    def stop(self):
        """Stop the bot"""
        if not self.running:
            return

        print("\n" + "="*60)
        print("SHUTTING DOWN")
        print("="*60)

        self.running = False

        # Stop monitoring
        self.monitor.stop()

        # Get final stats
        final_stats = self.position_manager.get_portfolio_summary()

        print(f"\nFinal Stats:")
        print(f"  Net Worth: ${final_stats['net_worth']:,.2f}")
        print(f"  Total PnL: ${final_stats['total_pnl']:,.2f}")
        print(f"  Total Trades: {final_stats['total_trades']}")
        print(f"  Open Positions: {final_stats['open_positions']}")

        # Send shutdown notification
        self.notifier.notify_bot_stopped(final_stats)

        print("\n✓ Bot stopped\n")

    def on_trade_detected(self, trade: TradeEvent):
        """
        Callback when new trade detected from target account

        Args:
            trade: Trade event from target
        """
        print("\n" + "="*60)
        print(f"📊 TRADE DETECTED")
        print("="*60)
        print(f"Market: {trade.market_title}")
        print(f"Side: {trade.side}")
        print(f"Size: {trade.size} @ {trade.price}")
        print(f"Outcome: {trade.outcome}")
        print("="*60)

        try:
            # Check circuit breakers first
            if not self.risk_manager.check_circuit_breakers():
                print(f"\n🚨 Circuit breaker active: {self.risk_manager.circuit_breaker_reason}")
                print("Trade skipped")
                return

            # Validate trade
            print("\n🔍 Validating trade...")
            validation_result = self.validator.validate_trade(trade, self.target_net_worth)

            if not validation_result.passed:
                if not config.VERBOSE_VALIDATION:
                    # Only print rejection if not already shown in summary
                    print(f"❌ Trade rejected: {validation_result.reason}")

                self.notifier.notify_trade_rejected(
                    trade_info={
                        'market_title': trade.market_title,
                        'side': trade.side,
                        'size': trade.size * trade.price
                    },
                    reason=validation_result.reason
                )
                return

            if not config.VERBOSE_VALIDATION:
                print(f"✓ Validation passed: {validation_result.reason}")

            # Calculate position size
            their_bet_usd = trade.size * trade.price
            our_bet_usd = self.position_manager.calculate_position_size(
                their_bet_usd,
                self.target_net_worth
            )

            print(f"\n💰 Position Sizing:")
            print(f"  Their bet: ${their_bet_usd:,.2f} ({their_bet_usd/self.target_net_worth*100:.2f}% of net worth)")
            print(f"  Our bet: ${our_bet_usd:,.2f} ({our_bet_usd/self.position_manager.get_net_worth()*100:.2f}% of net worth)")

            # Execute order
            print(f"\n📤 Executing order...")
            execution_result = self.executor.execute_order(trade, our_bet_usd)

            if execution_result.success:
                print(f"✓ Order executed: {execution_result.order_id}")

                # Update position manager
                self.position_manager.add_position(
                    condition_id=trade.condition_id,
                    asset=trade.asset,
                    side=trade.side,
                    size=our_bet_usd / trade.price,  # Convert USD to shares
                    price=trade.price
                )

                self.position_manager.record_trade({
                    'side': trade.side,
                    'size': our_bet_usd / trade.price,
                    'price': trade.price,
                    'asset': trade.asset,
                    'condition_id': trade.condition_id,
                    'order_id': execution_result.order_id
                })

                # Send notification
                self.notifier.notify_trade_executed(execution_result.details)

                # Print updated stats
                stats = self.position_manager.get_portfolio_summary()
                print(f"\n📊 Portfolio Update:")
                print(f"  Net Worth: ${stats['net_worth']:,.2f}")
                print(f"  Available: ${stats['available_capital']:,.2f}")
                print(f"  Open Positions: {stats['open_positions']}")
                print(f"  Total Trades: {stats['total_trades']}")

            else:
                print(f"❌ Order failed: {execution_result.error}")
                self.notifier.notify_error(f"Order execution failed: {execution_result.error}")

        except CircuitBreakerException as e:
            print(f"\n🚨 CIRCUIT BREAKER TRIGGERED: {e}")
            stats = self.position_manager.get_portfolio_summary()
            self.notifier.notify_circuit_breaker(str(e), stats)

        except Exception as e:
            print(f"\n❌ Error processing trade: {e}")
            self.notifier.notify_error(f"Error processing trade: {e}")

        print("\n" + "="*60 + "\n")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n⚠️  Received signal {signum}")
        self.running = False
