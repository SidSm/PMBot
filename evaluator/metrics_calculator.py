"""
Metrics calculator module
Contains all 9 evaluation criteria calculations
"""

from typing import List, Dict, Tuple, Optional
from collections import Counter
import statistics

import config
from evaluator.utils import days_ago_timestamp


class MetricsCalculator:
    """Calculates evaluation metrics for Polymarket accounts"""

    @staticmethod
    def calculate_total_pnl(closed_positions: List[Dict]) -> Tuple[float, bool]:
        """
        Calculate total realized PnL from closed positions

        Args:
            closed_positions: List of closed position objects

        Returns:
            Tuple of (pnl_value, pass/fail)
        """
        total_pnl = sum(float(pos.get('realizedPnl', 0)) for pos in closed_positions)
        passes = total_pnl >= config.THRESHOLDS['min_pnl']
        return total_pnl, passes

    @staticmethod
    def calculate_win_rate(closed_positions: List[Dict]) -> Tuple[float, bool, int]:
        """
        Calculate win rate excluding ties/pushes

        Args:
            closed_positions: List of closed position objects

        Returns:
            Tuple of (win_rate, pass/fail, num_ties)
        """
        wins = 0
        losses = 0
        ties = 0

        for pos in closed_positions:
            pnl = float(pos.get('realizedPnl', 0))

            if abs(pnl) < config.TIE_PUSH_THRESHOLD:
                ties += 1
            elif pnl > 0:
                wins += 1
            else:
                losses += 1

        total_decisive = wins + losses
        if total_decisive == 0:
            return 0.0, False, ties

        win_rate = (wins / total_decisive) * 100

        passes = (config.THRESHOLDS['min_win_rate'] <= win_rate <= config.THRESHOLDS['max_win_rate'])

        return win_rate, passes, ties

    @staticmethod
    def calculate_total_trades(trades: List[Dict]) -> Tuple[int, bool]:
        """
        Calculate total number of trades

        Args:
            trades: List of trade objects

        Returns:
            Tuple of (trade_count, pass/fail)
        """
        trade_count = len(trades)
        passes = (config.THRESHOLDS['min_trades'] <= trade_count <= config.THRESHOLDS['max_trades'])
        return trade_count, passes

    @staticmethod
    def calculate_account_age(trades: List[Dict]) -> Tuple[int, bool]:
        """
        Calculate account age based on first and last trade

        Args:
            trades: List of trade objects

        Returns:
            Tuple of (age_in_days, pass/fail)
        """
        if not trades:
            return 0, False

        timestamps = [int(trade.get('timestamp', 0)) for trade in trades if trade.get('timestamp')]

        if not timestamps:
            return 0, False

        first_trade = min(timestamps)
        last_trade = max(timestamps)

        age_seconds = last_trade - first_trade
        age_days = age_seconds // (24 * 60 * 60)

        passes = age_days >= config.THRESHOLDS['min_age_days']

        return age_days, passes

    @staticmethod
    def detect_niche_specialization(trades: List[Dict], closed_positions: List[Dict]) -> Tuple[str, float, bool]:
        """
        Detect if trader specializes in a niche (>40% concentration)

        Uses market titles to categorize trades

        Args:
            trades: List of trade objects
            closed_positions: List of closed position objects

        Returns:
            Tuple of (top_category, concentration_pct, pass/fail)
        """
        # Use titles from closed positions (more reliable than trades)
        titles = [pos.get('title', '').lower() for pos in closed_positions if pos.get('title')]

        if not titles:
            return "Unknown", 0.0, False

        # Keyword-based categorization
        categories = []
        for title in titles:
            category = MetricsCalculator._categorize_market(title)
            categories.append(category)

        # Count category occurrences
        category_counts = Counter(categories)
        top_category, top_count = category_counts.most_common(1)[0]

        concentration_pct = (top_count / len(categories)) * 100

        passes = concentration_pct >= config.THRESHOLDS['niche_concentration']

        return top_category, concentration_pct, passes

    @staticmethod
    def _categorize_market(title: str) -> str:
        """
        Categorize a market based on title keywords

        Args:
            title: Market title (lowercase)

        Returns:
            Category name
        """
        # Keyword mapping for categories
        categories_keywords = {
            'Politics': ['trump', 'biden', 'election', 'president', 'senate', 'congress', 'republican', 'democrat', '政治'],
            'Sports': ['nfl', 'nba', 'mlb', 'nhl', 'soccer', 'football', 'basketball', 'baseball', 'super bowl', 'world cup', 'championship'],
            'Crypto': ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'blockchain', 'defi', 'nft', 'solana', 'sol'],
            'Finance': ['stock', 'market', 'economy', 'fed', 'inflation', 'interest rate', 'recession', 'gdp', 's&p'],
            'Entertainment': ['movie', 'oscar', 'grammy', 'emmy', 'celebrity', 'actor', 'singer', 'album', 'box office'],
            'Technology': ['ai', 'artificial intelligence', 'tech', 'apple', 'google', 'microsoft', 'tesla', 'spacex'],
            'Weather': ['temperature', 'weather', 'hurricane', 'storm', 'climate', 'snow', 'rain'],
        }

        for category, keywords in categories_keywords.items():
            for keyword in keywords:
                if keyword in title:
                    return category

        return 'Other'

    @staticmethod
    def calculate_position_sizing_consistency(trades: List[Dict]) -> Tuple[float, float, bool]:
        """
        Calculate position sizing consistency using coefficient of variation

        Args:
            trades: List of trade objects

        Returns:
            Tuple of (cv_value, mean_size, pass/fail)
        """
        sizes = [float(trade.get('size', 0)) for trade in trades if trade.get('size')]

        if len(sizes) < 2:
            return 0.0, 0.0, False

        mean_size = statistics.mean(sizes)
        std_dev = statistics.stdev(sizes)

        if mean_size == 0:
            return 0.0, 0.0, False

        cv = std_dev / mean_size

        passes = cv <= config.THRESHOLDS['max_cv']

        return cv, mean_size, passes

    @staticmethod
    def calculate_recent_performance(closed_positions: List[Dict]) -> Tuple[float, bool]:
        """
        Calculate PnL from last 30 days

        Args:
            closed_positions: List of closed position objects

        Returns:
            Tuple of (recent_pnl, pass/fail)
        """
        cutoff_timestamp = days_ago_timestamp(config.RECENT_PERFORMANCE_DAYS)

        recent_pnl = 0.0
        for pos in closed_positions:
            timestamp = int(pos.get('timestamp', 0))
            if timestamp >= cutoff_timestamp:
                recent_pnl += float(pos.get('realizedPnl', 0))

        passes = recent_pnl > 0

        return recent_pnl, passes

    @staticmethod
    def check_single_win_dominance(closed_positions: List[Dict], total_pnl: float) -> Tuple[float, float, bool]:
        """
        Check if a single win makes up >50% of total PnL

        Args:
            closed_positions: List of closed position objects
            total_pnl: Total PnL (from calculate_total_pnl)

        Returns:
            Tuple of (max_win, max_win_pct, pass/fail)
        """
        if total_pnl <= 0:
            return 0.0, 0.0, False

        pnls = [float(pos.get('realizedPnl', 0)) for pos in closed_positions]
        winning_pnls = [pnl for pnl in pnls if pnl > 0]

        if not winning_pnls:
            return 0.0, 0.0, False

        max_win = max(winning_pnls)
        max_win_pct = (max_win / total_pnl) * 100

        passes = max_win_pct <= config.THRESHOLDS['max_single_win_pct']

        return max_win, max_win_pct, passes

    @staticmethod
    def check_liquid_markets(closed_positions: List[Dict]) -> Tuple[int, int, bool]:
        """
        Check if markets traded are still liquid/active

        Uses endDate to determine if market is still active

        Args:
            closed_positions: List of closed position objects

        Returns:
            Tuple of (liquid_count, total_markets, pass/fail)
        """
        from evaluator.utils import get_current_timestamp, parse_iso_date

        current_time = get_current_timestamp()
        liquid_count = 0
        total_markets = 0

        # Get unique markets
        unique_markets = {}
        for pos in closed_positions:
            condition_id = pos.get('conditionId')
            if condition_id and condition_id not in unique_markets:
                unique_markets[condition_id] = pos

        total_markets = len(unique_markets)

        if total_markets == 0:
            return 0, 0, False

        # Check if markets are still active (endDate in future or None)
        for condition_id, pos in unique_markets.items():
            end_date = pos.get('endDate')

            # If no endDate, consider liquid
            if end_date is None:
                liquid_count += 1
                continue

            # Parse endDate (could be ISO string or Unix timestamp)
            if isinstance(end_date, str):
                end_date_timestamp = parse_iso_date(end_date)
            else:
                end_date_timestamp = int(end_date)

            # If endDate is in the future, consider liquid
            if end_date_timestamp and end_date_timestamp > current_time:
                liquid_count += 1

        liquid_pct = (liquid_count / total_markets) * 100
        passes = liquid_pct >= config.THRESHOLDS['min_liquid_markets_pct']

        return liquid_count, total_markets, passes
