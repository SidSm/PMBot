#!/usr/bin/env python3
"""
Polymarket Copycat Trading Bot - Main Entry Point

Configuration is loaded from .env file
No command line arguments needed

Usage:
    python trader/main.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluator.utils import validate_address
import trader.config as config
from trader.copycat_bot import CopycatBot


def main():
    """Main entry point"""

    # Validate configuration
    if not config.TARGET_ACCOUNT:
        print("❌ TARGET_ACCOUNT not set in .env")
        print("\nPlease set TARGET_ACCOUNT in your .env file:")
        print("TARGET_ACCOUNT=0x1234567890abcdef1234567890abcdef12345678")
        sys.exit(1)

    # Validate target address
    if not validate_address(config.TARGET_ACCOUNT):
        print(f"❌ Invalid Ethereum address: {config.TARGET_ACCOUNT}")
        print("\nAddress must:")
        print("  - Start with '0x'")
        print("  - Be 42 characters long")
        print("  - Contain only hexadecimal characters")
        sys.exit(1)

    # Check private key for live trading
    if not config.DRY_RUN:
        if not config.POLYMARKET_PRIVATE_KEY:
            print("❌ POLYMARKET_PRIVATE_KEY not set in .env")
            print("\nLive trading requires your wallet's private key")
            print("Export from MetaMask: Account → Account details → Show private key")
            print("\nAdd to .env:")
            print("POLYMARKET_PRIVATE_KEY=0x1234...")
            sys.exit(1)

    # Display mode warning for dry-run
    if config.DRY_RUN:
        print("\n" + "="*60)
        print("⚠️  DRY RUN MODE - NO REAL TRADES WILL BE PLACED")
        print("="*60)
        print("This is a simulation. To trade live:")
        print("1. Set DRY_RUN=false in .env")
        print("2. Ensure POLYMARKET_PRIVATE_KEY is configured")
        print("="*60 + "\n")

    # Determine bankroll
    if config.BANKROLL_MODE == 'fixed':
        bankroll = config.FIXED_BANKROLL
        print(f"Using fixed bankroll: ${bankroll:,.2f}")
    else:
        # Dynamic mode - will use wallet balance
        print("Using dynamic bankroll mode (wallet balance)")
        bankroll = config.FIXED_BANKROLL  # Initial estimate

    try:
        # Initialize and start bot
        bot = CopycatBot(
            target_account=config.TARGET_ACCOUNT,
            initial_capital=bankroll
        )

        bot.start()

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(130)

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
