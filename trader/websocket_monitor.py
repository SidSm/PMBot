"""
Trade monitor for tracking target account activity.

Polls the Polymarket Data API for new trades from the target account.
"""

import time
import threading
from typing import Callable, Dict, List, Set
import requests

import trader.config as config


class TradeEvent:
    """Represents a trade event from target account"""

    def __init__(self, data: Dict):
        self.raw_data = data
        self.trader_address = data.get('proxyWallet', '').lower()
        self.side = data.get('side')  # BUY or SELL
        self.asset = data.get('asset')  # token ID
        self.condition_id = data.get('conditionId')
        self.size = float(data.get('size', 0))
        self.price = float(data.get('price', 0))
        self.timestamp = int(data.get('timestamp', 0))
        self.outcome = data.get('outcome')
        self.market_title = data.get('title', '')
        self.transaction_hash = data.get('transactionHash')

    def __repr__(self):
        return f"TradeEvent({self.side} {self.size} @ {self.price} - {self.market_title[:50]})"


class TradeMonitor:
    """Monitors target account for new trades by polling the Data API"""

    def __init__(self, target_account: str, on_trade_callback: Callable[[TradeEvent], None]):
        self.target_account = target_account.lower()
        self.on_trade_callback = on_trade_callback

        self.running = False
        self.poll_thread = None

        self.seen_tx_hashes: Set[str] = set()
        self.last_poll_timestamp = 0

    def start(self):
        """Start polling for trades"""
        self.running = True
        print(f"Starting trade monitor for {self.target_account}...")
        print(f"Polling every {config.POLLING_INTERVAL}s")
        self.poll_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.poll_thread.start()

    def stop(self):
        """Stop polling"""
        print("Stopping trade monitor...")
        self.running = False
        if self.poll_thread:
            self.poll_thread.join(timeout=5)

    def _polling_loop(self):
        """Poll Data API for new trades"""
        while self.running:
            try:
                trades = self._fetch_recent_trades()

                for trade in trades:
                    if trade.transaction_hash and trade.transaction_hash in self.seen_tx_hashes:
                        continue

                    if trade.timestamp <= self.last_poll_timestamp:
                        continue

                    if trade.transaction_hash:
                        self.seen_tx_hashes.add(trade.transaction_hash)
                    self.last_poll_timestamp = trade.timestamp

                    print(f"\nTrade detected: {trade}")
                    self.on_trade_callback(trade)

                # Prevent unbounded growth
                if len(self.seen_tx_hashes) > 10000:
                    self.seen_tx_hashes = set(list(self.seen_tx_hashes)[-5000:])

            except Exception as e:
                print(f"Polling error: {e}")

            time.sleep(config.POLLING_INTERVAL)

    def _fetch_recent_trades(self) -> List[TradeEvent]:
        """Fetch recent trades from Data API"""
        url = f"{config.POLYMARKET_DATA_API}/activity"
        params = {
            'user': self.target_account,
            'type': 'TRADE',
            'limit': 10,
            'sortDirection': 'DESC'
        }

        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()

        data = response.json()
        trades = []

        for item in data:
            try:
                trade = TradeEvent(item)
                trades.append(trade)
            except Exception as e:
                print(f"Error parsing trade: {e}")

        return trades
