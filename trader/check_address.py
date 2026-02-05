#!/usr/bin/env python3
"""
Check which address your private key corresponds to
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import trader.config as config

def main():
    if not config.POLYMARKET_PRIVATE_KEY:
        print("❌ POLYMARKET_PRIVATE_KEY not set in .env")
        sys.exit(1)

    try:
        from eth_account import Account

        account = Account.from_key(config.POLYMARKET_PRIVATE_KEY)
        address = account.address

        print("\n" + "="*60)
        print("WALLET ADDRESS FROM YOUR PRIVATE KEY")
        print("="*60)
        print(f"Address: {address}")
        print("="*60)

        # Check balance
        from trader.wallet_tracker import WalletTracker

        tracker = WalletTracker()
        summary = tracker.get_wallet_summary(address)

        if summary['total_net_worth'] is not None:
            print(f"\n💰 USDC Balance: ${summary['usdc_balance']:,.2f}")
            print(f"📈 Open Positions: ${summary['positions_value']:,.2f}")
            print(f"💵 Realized PnL: ${summary['realized_pnl']:,.2f}")
            print(f"🏆 Total Net Worth: ${summary['total_net_worth']:,.2f}")
        else:
            print("\n⚠️  Could not fetch balance")

        print(f"\nℹ️  Set this address in .env as TARGET_ACCOUNT to mirror your own trades:")
        print(f"TARGET_ACCOUNT={address}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
