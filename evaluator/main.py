#!/usr/bin/env python3
"""
Polymarket Account Evaluator - Main CLI Entry Point

Usage:
    python main.py <wallet_address>

Example:
    python main.py 0x1234567890abcdef1234567890abcdef12345678
"""

import sys
from evaluator import AccountEvaluator, EvaluationResult
from data_fetcher import PolymarketAPIError
from evaluator.utils import validate_address


def main():
    """Main CLI entry point"""

    # Check arguments
    if len(sys.argv) != 2:
        print("Usage: python main.py <wallet_address>")
        print("\nExample:")
        print("  python main.py 0x1234567890abcdef1234567890abcdef12345678")
        sys.exit(1)

    wallet_address = sys.argv[1]

    # Validate address format
    if not validate_address(wallet_address):
        print(f"❌ Invalid Ethereum address format: {wallet_address}")
        print("\nAddress must:")
        print("  - Start with '0x'")
        print("  - Be 42 characters long")
        print("  - Contain only hexadecimal characters")
        sys.exit(1)

    try:
        # Initialize evaluator
        evaluator = AccountEvaluator(wallet_address)

        # Run evaluation
        result = evaluator.run_evaluation()

        # Generate and print report
        report = evaluator.generate_report(result)
        print(report)

        # Exit with appropriate code
        if result.overall_pass:
            sys.exit(0)  # Success - all criteria met
        else:
            sys.exit(1)  # Failure - some criteria not met

    except PolymarketAPIError as e:
        print(f"\n❌ API Error: {e}")
        print("\nPossible causes:")
        print("  - Network connectivity issues")
        print("  - Polymarket API is down")
        print("  - Rate limiting")
        sys.exit(2)

    except KeyboardInterrupt:
        print("\n\n⚠️  Evaluation interrupted by user")
        sys.exit(130)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()
