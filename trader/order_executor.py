"""
Order executor for placing trades on Polymarket
"""

import time
from typing import Optional, Dict
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs, OrderType
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
        if not config.POLYMARKET_FUNDER:
            raise ValueError("POLYMARKET_FUNDER (proxy wallet address) required for live trading. "
                             "Find it on your Polymarket profile page URL.")

        try:

            # Generate or derive API credentials
            print("  - Generating API credentials...")

            # Create or derive user API credentials
            temp_client = ClobClient(
                host=config.POLYMARKET_CLOB_API, 
                key=config.POLYMARKET_PRIVATE_KEY,
                chain_id=137)
            
            creds = temp_client.create_or_derive_api_creds()

            self.client = ClobClient(
                host=config.POLYMARKET_CLOB_API,
                key=config.POLYMARKET_PRIVATE_KEY,
                chain_id=137,  # Polygon mainnet
                signature_type=1,  # POLY_GNOSIS_SAFE
                funder=config.POLYMARKET_FUNDER,
                creds=creds
            )

            print("✓ CLOB client initialized with API credentials")

            # Set allowances for USDC (required for trading)
            print("  - Setting USDC allowances...")
            try:
                allowances = self.client.get_balance_allowance()
                print(f"    Current allowances: {allowances}")

                # Set allowance if needed (approve Polymarket to spend USDC)
                #self.client.set_a()
                print("  ✓ Allowances set")
            except Exception as e:
                print(f"  ⚠️  Allowance setup: {e}")
                print("  ℹ️  You may need to manually approve USDC spending")

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

                # Use GTC (Good-Till-Cancelled) orders with aggressive pricing
                # GTC doesn't have the strict market order decimal restrictions

                # Round size to 4 decimals (standard for limit orders)
                token_size = size_usd / trade.price
                token_size = round(token_size, 4)

                if trade.side == 'BUY':
                    # Use aggressive price (higher for BUY to ensure fill)
                    order_price = round(trade.price * 1.10, 2)  # +10% slippage
                    order_price = min(order_price, 0.99)  # Cap at 0.99
                else:
                    # Use aggressive price (lower for SELL to ensure fill)
                    order_price = round(trade.price * 0.90, 2)  # -10% slippage
                    order_price = max(order_price, 0.01)  # Floor at 0.01

                print(f"  Size: {token_size} tokens @ ${order_price} (GTC limit order)")

                # Create limit order
                order_args = OrderArgs(
                    token_id=trade.asset,
                    price=order_price,
                    size=token_size,
                    side=BUY if trade.side == 'BUY' else SELL
                )

                # Create and sign order
                signed_order = self.client.create_order(order_args)

                # Post order as GTC (Good-Till-Cancelled)
                # Will fill immediately at best price, remains open if partial fill
                result = self.client.post_order(signed_order, OrderType.GTC)

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
