"""
Order executor for placing trades on Polymarket
"""

import time
from typing import Optional, Dict
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs
from py_clob_client.order_builder.constants import BUY, SELL

import trader.config as config
from trader.websocket_monitor import TradeEvent


class OrderExecutionResult:
    """Result of order execution attempt"""

    def __init__(self, success: bool, order_id: Optional[str] = None, error: Optional[str] = None,
                 details: Optional[Dict] = None):
        self.success = success
        self.order_id = order_id
        self.error = error
        self.details = details or {}

    def __bool__(self):
        return self.success

    def __repr__(self):
        if self.success:
            return f"✓ Order executed: {self.order_id}"
        else:
            return f"✗ Order failed: {self.error}"


class OrderExecutor:
    """Executes orders on Polymarket via CLOB API"""

    def __init__(self, dry_run: bool = True):
        """
        Initialize order executor

        Args:
            dry_run: If True, simulate orders without placing them
        """
        self.dry_run = dry_run
        self.client = None

        if not dry_run:
            self._initialize_client()

    def _initialize_client(self):
        """Initialize Polymarket CLOB client"""
        if not config.POLYMARKET_PRIVATE_KEY:
            raise ValueError("POLYMARKET_PRIVATE_KEY required for live trading")

        try:
            # Initialize CLOB client
            # The client will automatically generate API credentials from private key
            self.client = ClobClient(
                host=config.POLYMARKET_CLOB_API,
                key=config.POLYMARKET_PRIVATE_KEY,
                chain_id=137,  # Polygon mainnet
            )
            print("✓ CLOB client initialized")

        except Exception as e:
            raise Exception(f"Failed to initialize CLOB client: {e}")

    def execute_order(self, trade: TradeEvent, size_usd: float) -> OrderExecutionResult:
        """
        Execute market order to copy trade

        Args:
            trade: Original trade event from target account
            size_usd: Our position size in USD

        Returns:
            OrderExecutionResult with execution details
        """
        if self.dry_run:
            return self._simulate_order(trade, size_usd)

        return self._execute_real_order(trade, size_usd)

    def _simulate_order(self, trade: TradeEvent, size_usd: float) -> OrderExecutionResult:
        """Simulate order execution in dry-run mode"""
        print(f"\n{'='*60}")
        print(f"🧪 DRY RUN - Simulating Order")
        print(f"{'='*60}")
        print(f"Market: {trade.market_title}")
        print(f"Outcome: {trade.outcome}")
        print(f"Side: {trade.side}")
        print(f"Size: ${size_usd:,.2f}")
        print(f"Price: {trade.price}")
        print(f"Asset: {trade.asset}")
        print(f"Condition ID: {trade.condition_id}")
        print(f"{'='*60}\n")

        # Simulate successful execution
        fake_order_id = f"DRY_RUN_{int(time.time())}"

        return OrderExecutionResult(
            success=True,
            order_id=fake_order_id,
            details={
                'side': trade.side,
                'size': size_usd,
                'price': trade.price,
                'asset': trade.asset,
                'condition_id': trade.condition_id,
                'market_title': trade.market_title,
                'dry_run': True
            }
        )

    def _execute_real_order(self, trade: TradeEvent, size_usd: float) -> OrderExecutionResult:
        """Execute actual order on Polymarket"""
        print(f"\n{'='*60}")
        print(f"📤 LIVE ORDER - Executing")
        print(f"{'='*60}")

        attempts = 0
        max_attempts = config.EXECUTION['max_retries']
        total_timeout = config.EXECUTION['total_timeout']
        retry_delay = config.EXECUTION['retry_delay']

        start_time = time.time()

        while attempts < max_attempts:
            elapsed = time.time() - start_time
            if elapsed >= total_timeout:
                return OrderExecutionResult(
                    success=False,
                    error=f"Timeout after {elapsed:.1f}s"
                )

            attempts += 1

            try:
                print(f"Attempt {attempts}/{max_attempts}...")

                # Create market order
                order_args = MarketOrderArgs(
                    token_id=trade.asset,
                    amount=size_usd,
                    side=BUY if trade.side == 'BUY' else SELL,
                    feeRateBps=0  # Will be calculated by client
                )

                # Create and sign order
                signed_order = self.client.create_market_order(order_args)

                # Post order to CLOB
                result = self.client.post_order(signed_order, order_type='FOK')

                if result and result.get('orderID'):
                    print(f"✓ Order executed: {result['orderID']}")

                    return OrderExecutionResult(
                        success=True,
                        order_id=result['orderID'],
                        details={
                            'side': trade.side,
                            'size': size_usd,
                            'price': trade.price,
                            'asset': trade.asset,
                            'condition_id': trade.condition_id,
                            'market_title': trade.market_title,
                            'result': result
                        }
                    )
                else:
                    error_msg = result.get('error', 'Unknown error')
                    print(f"✗ Order failed: {error_msg}")

                    if attempts < max_attempts:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return OrderExecutionResult(
                            success=False,
                            error=error_msg
                        )

            except Exception as e:
                print(f"✗ Error: {e}")

                if attempts < max_attempts:
                    time.sleep(retry_delay)
                    continue
                else:
                    return OrderExecutionResult(
                        success=False,
                        error=str(e)
                    )

        return OrderExecutionResult(
            success=False,
            error=f"Failed after {attempts} attempts"
        )

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Get status of an order

        Args:
            order_id: Order ID to check

        Returns:
            Order status dict or None
        """
        if self.dry_run or not self.client:
            return None

        try:
            status = self.client.get_order(order_id)
            return status
        except Exception as e:
            print(f"Error getting order status: {e}")
            return None
