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
from trader.wallet_tracker import WalletTracker


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

        # Initialize wallet tracker
        self.wallet_tracker = WalletTracker()

        # Get wallet balances at startup
        print("\n📊 Fetching wallet balances...")
        self._fetch_wallet_balances()

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

        print(f"✓ All components initialized\n")

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _fetch_wallet_balances(self):
        """Fetch and display wallet balances for both accounts"""

        # Get target account balance
        print(f"\n🎯 Target Account: {self.target_account}")
        target_summary = self.wallet_tracker.get_wallet_summary(self.target_account)

        if target_summary['total_net_worth'] is not None:
            self.target_net_worth = target_summary['total_net_worth']
            print(f"  💰 USDC Balance: ${target_summary['usdc_balance']:,.2f}")
            print(f"  📈 Open Positions: ${target_summary['positions_value']:,.2f}")
            print(f"  💵 Realized PnL: ${target_summary['realized_pnl']:,.2f}")
            print(f"  🏆 Total Net Worth: ${target_summary['total_net_worth']:,.2f}")
        else:
            print(f"  ⚠️  Could not fetch balance, using default estimate")
            self.target_net_worth = config.TARGET_INITIAL_CAPITAL
            print(f"  🏆 Estimated Net Worth: ${self.target_net_worth:,.2f}")

        # Get our wallet balance (if we have private key)
        if config.POLYMARKET_PRIVATE_KEY and not config.DRY_RUN:
            try:
                from eth_account import Account
                our_address = Account.from_key(config.POLYMARKET_PRIVATE_KEY).address

                print(f"\n💼 Our Account (EOA): {our_address}")
                our_summary = self.wallet_tracker.get_wallet_summary(our_address, try_find_proxy=True)

                if our_summary.get('proxy_address'):
                    print(f"  🔗 Proxy Wallet: {our_summary['proxy_address']}")

                if our_summary['total_net_worth'] is not None:
                    print(f"  💰 USDC Balance: ${our_summary['usdc_balance']:,.2f}")
                    print(f"  📈 Open Positions: ${our_summary['positions_value']:,.2f}")
                    print(f"  💵 Realized PnL: ${our_summary['realized_pnl']:,.2f}")
                    print(f"  🏆 Total Net Worth: ${our_summary['total_net_worth']:,.2f}")

                    # Update bankroll if dynamic mode
                    if config.BANKROLL_MODE == 'dynamic':
                        self.initial_capital = our_summary['total_net_worth']
                        print(f"  ℹ️  Dynamic mode: Using actual net worth as bankroll")
                else:
                    print(f"  ⚠️  Could not fetch balance")

            except Exception as e:
                print(f"  ⚠️  Could not fetch our wallet balance: {e}")
        else:
            print(f"\n💼 Our Account: {'DRY RUN MODE' if config.DRY_RUN else 'No private key'}")
            print(f"  🏆 Configured Bankroll: ${self.initial_capital:,.2f}")

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
