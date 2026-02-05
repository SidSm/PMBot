"""
Main evaluator module
Orchestrates data fetching and metrics calculation
"""

from typing import Dict, Any
from datetime import datetime, timezone

from data_fetcher import DataFetcher, PolymarketAPIError
from metrics_calculator import MetricsCalculator
from evaluator.utils import format_currency, format_percentage


class EvaluationResult:
    """Stores evaluation results for an account"""

    def __init__(self):
        self.address = ""
        self.evaluated_at = datetime.now(timezone.utc)

        # Metrics
        self.total_pnl = 0.0
        self.total_pnl_pass = False

        self.win_rate = 0.0
        self.win_rate_pass = False
        self.num_ties = 0

        self.total_trades = 0
        self.total_trades_pass = False

        self.account_age_days = 0
        self.account_age_pass = False

        self.niche_category = ""
        self.niche_concentration = 0.0
        self.niche_pass = False

        self.position_cv = 0.0
        self.mean_bet_size = 0.0
        self.position_cv_pass = False

        self.recent_pnl = 0.0
        self.recent_pnl_pass = False

        self.max_win = 0.0
        self.max_win_pct = 0.0
        self.max_win_pass = False

        self.liquid_count = 0
        self.total_markets = 0
        self.liquid_markets_pass = False

    @property
    def overall_pass(self) -> bool:
        """Check if all criteria pass"""
        return all([
            self.total_pnl_pass,
            self.win_rate_pass,
            self.total_trades_pass,
            self.account_age_pass,
            self.niche_pass,
            self.position_cv_pass,
            self.recent_pnl_pass,
            self.max_win_pass,
            self.liquid_markets_pass,
        ])

    @property
    def criteria_met(self) -> int:
        """Count how many criteria passed"""
        return sum([
            self.total_pnl_pass,
            self.win_rate_pass,
            self.total_trades_pass,
            self.account_age_pass,
            self.niche_pass,
            self.position_cv_pass,
            self.recent_pnl_pass,
            self.max_win_pass,
            self.liquid_markets_pass,
        ])


class AccountEvaluator:
    """Main evaluator class for Polymarket accounts"""

    def __init__(self, user_address: str):
        """
        Initialize evaluator

        Args:
            user_address: Ethereum wallet address to evaluate
        """
        self.user_address = user_address
        self.fetcher = DataFetcher()
        self.calculator = MetricsCalculator()

    def run_evaluation(self) -> EvaluationResult:
        """
        Run complete evaluation on the account

        Returns:
            EvaluationResult object with all metrics

        Raises:
            PolymarketAPIError: If data fetching fails
        """
        result = EvaluationResult()
        result.address = self.user_address

        print(f"Fetching data for {self.user_address}...")

        # Fetch all data
        print("  - Fetching trades...")
        trades = self.fetcher.fetch_user_trades(self.user_address)

        print("  - Fetching closed positions...")
        closed_positions = self.fetcher.fetch_closed_positions(self.user_address)

        print(f"  - Found {len(trades)} trades and {len(closed_positions)} closed positions")

        if not trades and not closed_positions:
            print("⚠️  No trading history found for this address")
            return result

        print("\nCalculating metrics...")

        # Calculate all metrics
        result.total_pnl, result.total_pnl_pass = \
            self.calculator.calculate_total_pnl(closed_positions)

        result.win_rate, result.win_rate_pass, result.num_ties = \
            self.calculator.calculate_win_rate(closed_positions)

        result.total_trades, result.total_trades_pass = \
            self.calculator.calculate_total_trades(trades)

        result.account_age_days, result.account_age_pass = \
            self.calculator.calculate_account_age(trades)

        result.niche_category, result.niche_concentration, result.niche_pass = \
            self.calculator.detect_niche_specialization(trades, closed_positions)

        result.position_cv, result.mean_bet_size, result.position_cv_pass = \
            self.calculator.calculate_position_sizing_consistency(trades)

        result.recent_pnl, result.recent_pnl_pass = \
            self.calculator.calculate_recent_performance(closed_positions)

        result.max_win, result.max_win_pct, result.max_win_pass = \
            self.calculator.check_single_win_dominance(closed_positions, result.total_pnl)

        result.liquid_count, result.total_markets, result.liquid_markets_pass = \
            self.calculator.check_liquid_markets(closed_positions)

        print("✓ Evaluation complete\n")

        return result

    @staticmethod
    def generate_report(result: EvaluationResult) -> str:
        """
        Generate formatted evaluation report

        Args:
            result: EvaluationResult object

        Returns:
            Formatted report string
        """
        def status_icon(passed: bool) -> str:
            return "✅" if passed else "❌"

        report_lines = [
            "=" * 50,
            "POLYMARKET ACCOUNT EVALUATION",
            "=" * 50,
            f"Address: {result.address}",
            f"Evaluated: {result.evaluated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "-" * 50,
            "METRICS BREAKDOWN",
            "-" * 50,
            f"{status_icon(result.total_pnl_pass)} Total PnL: {format_currency(result.total_pnl)} ({'Pass' if result.total_pnl_pass else 'Fail'})",
            f"{status_icon(result.win_rate_pass)} Win Rate: {format_percentage(result.win_rate)} ({'Pass' if result.win_rate_pass else 'Fail'})",
            f"   └─ Ties/Pushes: {result.num_ties} trades",
            f"{status_icon(result.total_trades_pass)} Total Trades: {result.total_trades} ({'Pass' if result.total_trades_pass else 'Fail'})",
            f"{status_icon(result.account_age_pass)} Account Age: {result.account_age_days} days ({'Pass' if result.account_age_pass else 'Fail'})",
            f"{status_icon(result.niche_pass)} Niche Specialization: {result.niche_category} ({format_percentage(result.niche_concentration)}) ({'Pass' if result.niche_pass else 'Fail'})",
            f"{status_icon(result.position_cv_pass)} Position Sizing CV: {result.position_cv:.2f} ({'Pass' if result.position_cv_pass else 'Fail'})",
            f"   └─ Mean bet size: {format_currency(result.mean_bet_size)}",
            f"{status_icon(result.recent_pnl_pass)} Recent 30d PnL: {format_currency(result.recent_pnl)} ({'Pass' if result.recent_pnl_pass else 'Fail'})",
            f"{status_icon(result.max_win_pass)} No Single Massive Win: Largest = {format_percentage(result.max_win_pct)} ({'Pass' if result.max_win_pass else 'Fail'})",
            f"{status_icon(result.liquid_markets_pass)} Liquid Markets: {result.liquid_count}/{result.total_markets} tradeable ({'Pass' if result.liquid_markets_pass else 'Fail'})",
            "",
            "-" * 50,
            f"OVERALL RESULT: {status_icon(result.overall_pass)} {'✓ PASS' if result.overall_pass else 'FAIL'} ({result.criteria_met}/9 criteria)",
            "-" * 50,
        ]

        return "\n".join(report_lines)
