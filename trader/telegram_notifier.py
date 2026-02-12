"""
Telegram notifier for sending alerts and updates
"""

import asyncio
import threading
from typing import Optional
from html import escape
from telegram import Bot
from telegram.error import TelegramError

import trader.config as config


class TelegramNotifier:
    """Sends notifications via Telegram bot"""

    def __init__(self):
        """Initialize Telegram bot"""
        self.bot = None
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.enabled = False
        self.loop = None
        self.loop_thread = None

        if config.TELEGRAM_BOT_TOKEN and self.chat_id:
            try:
                if not config.ENABLE_TELEGRAM:
                    print("x Telegram notifications disabled")
                else:
                    self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
                    self._start_event_loop()
                    self.enabled = True
                    print("✓ Telegram notifications enabled")
            except Exception as e:
                print(f"⚠️  Telegram initialization failed: {e}")
        else:
            print("⚠️  Telegram not configured (missing token or chat_id)")

    def _start_event_loop(self):
        """Start a dedicated event loop for Telegram in separate thread"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()

        # Wait for loop to be ready
        import time
        while self.loop is None:
            time.sleep(0.01)

    def send_message(self, message: str):
        """
        Send a message via Telegram

        Args:
            message: Message text to send
        """
        if not self.enabled or not self.loop or not config.ENABLE_TELEGRAM:
            return

        try:
            # Schedule coroutine in the dedicated event loop
            future = asyncio.run_coroutine_threadsafe(
                self._send_async(message),
                self.loop
            )
            # Wait for completion with timeout
            future.result(timeout=5)
        except Exception as e:
            print(f"Telegram send error: {e}")

    async def _send_async(self, message: str):
        """Async message sender"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
        except TelegramError as e:
            print(f"Telegram API error: {e}")

    def notify_trade_executed(self, details: dict):
        """
        Notify about executed trade

        Args:
            details: Trade execution details
        """
        if not config.TELEGRAM['notify_trades'] or not config.ENABLE_TELEGRAM:
            return

        dry_run_tag = "🧪 DRY RUN" if details.get('dry_run') else "✅ LIVE"
        market_title = escape(details.get('market_title', 'Unknown')[:100])
        latency = details.get('latency_s', 0)
        their_bet = details.get('their_bet_usd', 0)
        our_bet = details.get('our_bet_usd', 0)
        outcome = escape(details.get('outcome', 'N/A') or 'N/A')

        message = f"""{dry_run_tag} <b>Trade Executed</b>

<b>Market:</b> {market_title}
<b>Outcome:</b> {outcome}
<b>Side:</b> {details.get('side')}
<b>Price:</b> {details.get('price', 0):.4f}

<b>Their bet:</b> ${their_bet:,.2f}
<b>Our bet:</b> ${our_bet:,.2f}

<b>Latency:</b> {latency:.1f}s
<b>Order ID:</b> <code>{details.get('order_id', 'N/A')}</code>"""
        self.send_message(message)

    def notify_trade_rejected(self, trade_info: dict, failures: list, trade_timestamp: int = 0):
        """
        Notify about rejected trade with all failure details

        Args:
            trade_info: Trade information
            failures: List of failure reason strings
            trade_timestamp: Unix timestamp of the target's trade
        """
        if not config.TELEGRAM['notify_rejections'] or not config.ENABLE_TELEGRAM:
            return

        market_title = escape(trade_info.get('market_title', 'Unknown')[:100])
        outcome = escape(trade_info.get('outcome', 'N/A') or 'N/A')

        # Calculate latency
        latency_str = ""
        if trade_timestamp > 0:
            import time
            latency = time.time() - trade_timestamp
            latency_str = f"\n<b>Latency at rejection:</b> {latency:.1f}s"

        # Format all failures
        failures_text = ""
        for f in failures:
            failures_text += f"\n• {escape(f)}"

        message = f"""❌ <b>Trade Rejected</b> ({len(failures)} check{'s' if len(failures) != 1 else ''} failed)

<b>Market:</b> {market_title}
<b>Outcome:</b> {outcome}
<b>Side:</b> {trade_info.get('side')}
<b>Price:</b> {trade_info.get('price', 0):.4f}
<b>Size:</b> ${trade_info.get('size', 0):,.2f}{latency_str}

<b>Failed checks:</b>{failures_text}"""
        self.send_message(message)

    def notify_circuit_breaker(self, reason: str, stats: dict):
        """
        Notify about circuit breaker activation

        Args:
            reason: Circuit breaker reason
            stats: Current portfolio stats
        """
        if not config.TELEGRAM['notify_circuit_breakers'] or not config.ENABLE_TELEGRAM:
            return

        message = f"""
🚨 <b>CIRCUIT BREAKER ACTIVATED</b>

<b>Reason:</b> {reason}

<b>Portfolio Status:</b>
• Net Worth: ${stats.get('net_worth', 0):,.2f}
• Daily PnL: ${stats.get('daily_pnl', 0):,.2f}
• Drawdown: {stats.get('drawdown_pct', 0):.1f}%
• Total PnL: ${stats.get('total_pnl', 0):,.2f}

<b>Trading paused until conditions improve.</b>
"""
        self.send_message(message.strip())

    def notify_error(self, error_msg: str):
        """
        Notify about system error

        Args:
            error_msg: Error message
        """
        if not config.TELEGRAM['notify_errors'] or not config.ENABLE_TELEGRAM:
            return

        message = f"""
⚠️ <b>System Error</b>

<code>{error_msg}</code>
"""
        self.send_message(message.strip())

    def notify_daily_summary(self, stats: dict):
        """
        Send daily performance summary

        Args:
            stats: Portfolio statistics
        """
        if not config.TELEGRAM['notify_daily_summary'] or not config.ENABLE_TELEGRAM:
            return

        message = f"""
📊 <b>Daily Summary</b>

<b>Portfolio:</b>
• Net Worth: ${stats.get('net_worth', 0):,.2f}
• Available: ${stats.get('available_capital', 0):,.2f}
• Open Positions: {stats.get('open_positions', 0)}

<b>Performance:</b>
• Total PnL: ${stats.get('total_pnl', 0):,.2f}
• Daily PnL: ${stats.get('daily_pnl', 0):,.2f}
• Drawdown: {stats.get('drawdown_pct', 0):.1f}%

<b>Activity:</b>
• Total Trades: {stats.get('total_trades', 0)}
"""
        self.send_message(message.strip())

    def notify_bot_started(self, target_account: str, config_summary: dict):
        """
        Notify when bot starts

        Args:
            target_account: Account being copied
            config_summary: Configuration summary
        """
        dry_run = "🧪 DRY RUN MODE" if config.DRY_RUN else "✅ LIVE TRADING"

        message = f"""
🤖 <b>Copycat Bot Started</b>

<b>Mode:</b> {dry_run}
<b>Target:</b> <code>{target_account}</code>
<b>Bankroll:</b> ${config_summary.get('bankroll', 0):,.2f} ({config_summary.get('mode', 'fixed')})

<b>Monitoring for trades...</b>
"""
        self.send_message(message.strip())

    def notify_bot_stopped(self, final_stats: dict):
        """
        Notify when bot stops

        Args:
            final_stats: Final portfolio statistics
        """
        message = f"""
🛑 <b>Copycat Bot Stopped</b>

<b>Final Stats:</b>
• Net Worth: ${final_stats.get('net_worth', 0):,.2f}
• Total PnL: ${final_stats.get('total_pnl', 0):,.2f}
• Total Trades: {final_stats.get('total_trades', 0)}

<b>Trading session ended.</b>
"""
        self.send_message(message.strip())

    def __del__(self):
        """Cleanup event loop on deletion"""
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
