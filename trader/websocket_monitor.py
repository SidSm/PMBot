"""
WebSocket monitor for tracking target account trades
Falls back to polling if WebSocket unavailable
"""

import json
import time
import threading
from typing import Callable, Optional, Dict, List
import websocket
import requests
from datetime import datetime

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
    """Monitors target account for new trades via WebSocket or polling"""

    def __init__(self, target_account: str, on_trade_callback: Callable[[TradeEvent], None]):
        """
        Initialize trade monitor

        Args:
            target_account: Ethereum address to monitor
            on_trade_callback: Function to call when new trade detected
        """
        self.target_account = target_account.lower()
        self.on_trade_callback = on_trade_callback

        self.running = False
        self.ws = None
        self.ws_thread = None
        self.poll_thread = None

        self.use_websocket = config.USE_WEBSOCKET
        self.seen_tx_hashes = set()  # Duplicate detection
        self.last_trade_timestamp = 0

        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10

    def start(self):
        """Start monitoring (WebSocket or polling)"""
        self.running = True

        if self.use_websocket:
            print(f"Starting WebSocket monitor for {self.target_account}...")
            self._start_websocket()
        else:
            print(f"Starting polling monitor for {self.target_account}...")
            self._start_polling()

    def stop(self):
        """Stop monitoring"""
        print("Stopping trade monitor...")
        self.running = False

        if self.ws:
            self.ws.close()

        if self.ws_thread:
            self.ws_thread.join(timeout=5)

        if self.poll_thread:
            self.poll_thread.join(timeout=5)

    def _start_websocket(self):
        """Start WebSocket connection"""
        self.ws_thread = threading.Thread(target=self._websocket_loop, daemon=True)
        self.ws_thread.start()

    def _websocket_loop(self):
        """WebSocket connection loop with reconnection"""
        while self.running and self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                self._connect_websocket()
            except Exception as e:
                print(f"WebSocket error: {e}")
                self.reconnect_attempts += 1

                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    print(f"WebSocket failed after {self.max_reconnect_attempts} attempts, falling back to polling")
                    self.use_websocket = False
                    self._start_polling()
                    break

                print(f"Reconnecting in {config.WS_RECONNECT_DELAY}s... (attempt {self.reconnect_attempts})")
                time.sleep(config.WS_RECONNECT_DELAY)

    def _connect_websocket(self):
        """Establish WebSocket connection"""
        websocket.enableTrace(False)

        self.ws = websocket.WebSocketApp(
            config.POLYMARKET_WS_URL,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close
        )

        self.ws.run_forever(ping_interval=config.WS_PING_INTERVAL)

    def _on_ws_open(self, ws):
        """WebSocket connection opened"""
        print("✓ WebSocket connected")
        self.reconnect_attempts = 0

        # Subscribe to trades activity
        subscribe_msg = {
            "subscriptions": [
                {
                    "topic": "activity",
                    "type": "trades"
                }
            ]
        }
        ws.send(json.dumps(subscribe_msg))
        print("✓ Subscribed to trades activity")

    def _on_ws_message(self, ws, message):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)

            # Check if it's a trade event
            if isinstance(data, dict) and data.get('proxyWallet'):
                trader_address = data.get('proxyWallet', '').lower()

                # Filter for target account only
                if trader_address == self.target_account:
                    trade = TradeEvent(data)

                    # Duplicate detection
                    if trade.transaction_hash in self.seen_tx_hashes:
                        return

                    self.seen_tx_hashes.add(trade.transaction_hash)
                    self.last_trade_timestamp = trade.timestamp

                    print(f"\n🔔 New trade detected: {trade}")
                    self.on_trade_callback(trade)

        except json.JSONDecodeError:
            pass  # Ignore non-JSON messages
        except Exception as e:
            print(f"Error processing message: {e}")

    def _on_ws_error(self, ws, error):
        """WebSocket error handler"""
        print(f"WebSocket error: {error}")

    def _on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket connection closed"""
        print(f"WebSocket closed (code: {close_status_code})")

    def _start_polling(self):
        """Start polling fallback"""
        self.poll_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.poll_thread.start()

    def _polling_loop(self):
        """Poll Data API for new trades"""
        print(f"Polling Data API every {config.POLLING_INTERVAL}s")

        while self.running:
            try:
                trades = self._fetch_recent_trades()

                for trade in trades:
                    # Duplicate detection
                    if trade.transaction_hash in self.seen_tx_hashes:
                        continue

                    # Only process trades newer than last seen
                    if trade.timestamp <= self.last_trade_timestamp:
                        continue

                    self.seen_tx_hashes.add(trade.transaction_hash)
                    self.last_trade_timestamp = trade.timestamp

                    print(f"\n🔔 New trade detected: {trade}")
                    self.on_trade_callback(trade)

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
