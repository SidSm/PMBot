#!/usr/bin/env python3
"""
Polymarket Copycat Trading Bot - Main CLI Entry Point

Usage:
    python trader/main.py --target <address> [options]

Examples:
    # Dry run with fixed bankroll
    python trader/main.py --target 0x123... --bankroll 1000 --dry-run

    # Live trading
    python trader/main.py --target 0x123... --bankroll 1000

    # Dynamic bankroll mode
    python trader/main.py --target 0x123... --bankroll-mode dynamic
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import validate_address
import trader.config as config
from trader.copycat_bot import CopycatBot


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Polymarket Copycat Trading Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run mode (paper trading)
  python trader/main.py --target 0xABC... --dry-run

  # Live trading with $1000 bankroll
  python trader/main.py --target 0xABC... --bankroll 1000

  # Dynamic bankroll (use wallet balance)
  python trader/main.py --target 0xABC... --bankroll-mode dynamic
        """
    )

    parser.add_argument(
        '--target',
        type=str,
        required=True,
        help='Ethereum address of account to copy (0x...)'
    )

    parser.add_argument(
        '--bankroll',
        type=float,
        default=None,
        help='Starting bankroll in USD (for fixed mode)'
    )

    parser.add_argument(
        '--bankroll-mode',
        type=str,
        choices=['fixed', 'dynamic'],
        default=None,
        help='Bankroll mode: fixed or dynamic (from wallet)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry-run mode (paper trading, no real orders)'
    )

    parser.add_argument(
        '--no-websocket',
        action='store_true',
        help='Disable WebSocket, use polling only'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()

    # Validate target address
    if not validate_address(args.target):
        print(f"❌ Invalid Ethereum address: {args.target}")
        print("\nAddress must:")
        print("  - Start with '0x'")
        print("  - Be 42 characters long")
        print("  - Contain only hexadecimal characters")
        sys.exit(1)

    # Override config with command line args
    if args.dry_run:
        config.DRY_RUN = True

    if args.bankroll_mode:
        config.BANKROLL_MODE = args.bankroll_mode

    if args.no_websocket:
        config.USE_WEBSOCKET = False

    # Determine bankroll
    if args.bankroll:
        bankroll = args.bankroll
    elif config.BANKROLL_MODE == 'fixed':
        bankroll = config.FIXED_BANKROLL
    else:
        # Dynamic mode - will use wallet balance
        print("⚠️  Dynamic bankroll mode: will use wallet balance")
        bankroll = config.FIXED_BANKROLL  # Initial estimate

    # Validate configuration
    if not config.DRY_RUN:
        if not config.POLYMARKET_PRIVATE_KEY:
            print("❌ POLYMARKET_PRIVATE_KEY not set in .env")
            print("Live trading requires your wallet's private key")
            print("Export from MetaMask: Account → Account details → Show private key")
            sys.exit(1)

    # Display warnings for dry-run
    if config.DRY_RUN:
        print("\n" + "="*60)
        print("⚠️  DRY RUN MODE - NO REAL TRADES WILL BE PLACED")
        print("="*60)
        print("This is a simulation. To trade live, remove --dry-run flag")
        print("and ensure API keys are configured in .env")
        print("="*60 + "\n")

    try:
        # Initialize and start bot
        bot = CopycatBot(
            target_account=args.target,
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
