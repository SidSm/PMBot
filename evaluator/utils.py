"""
Utility functions for Polymarket Account Evaluator
"""

from datetime import datetime, timezone
from typing import Optional


def parse_timestamp(timestamp: int) -> datetime:
    """
    Convert Unix timestamp to datetime object

    Args:
        timestamp: Unix timestamp in seconds

    Returns:
        datetime object in UTC
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def get_current_timestamp() -> int:
    """
    Get current Unix timestamp

    Returns:
        Current timestamp in seconds
    """
    return int(datetime.now(timezone.utc).timestamp())


def days_ago_timestamp(days: int) -> int:
    """
    Get Unix timestamp for N days ago

    Args:
        days: Number of days in the past

    Returns:
        Unix timestamp in seconds
    """
    current = datetime.now(timezone.utc)
    past = current.timestamp() - (days * 24 * 60 * 60)
    return int(past)


def format_currency(amount: float) -> str:
    """
    Format amount as USD currency

    Args:
        amount: Dollar amount

    Returns:
        Formatted string (e.g., "$1,234.56")
    """
    if amount >= 0:
        return f"${amount:,.2f}"
    else:
        return f"-${abs(amount):,.2f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Format value as percentage

    Args:
        value: Percentage value (e.g., 62.5 for 62.5%)
        decimals: Number of decimal places

    Returns:
        Formatted string (e.g., "62.5%")
    """
    return f"{value:.{decimals}f}%"


def validate_address(address: str) -> bool:
    """
    Validate Ethereum address format

    Args:
        address: Ethereum wallet address

    Returns:
        True if valid format, False otherwise
    """
    if not address.startswith('0x'):
        return False
    if len(address) != 42:
        return False
    try:
        int(address[2:], 16)
        return True
    except ValueError:
        return False


def parse_iso_date(date_string: str) -> Optional[int]:
    """
    Parse ISO 8601 date string to Unix timestamp

    Args:
        date_string: ISO 8601 date string (e.g., "2026-02-08T00:00:00Z")

    Returns:
        Unix timestamp in seconds, or None if parsing fails
    """
    if not date_string:
        return None

    try:
        # Handle ISO 8601 format with Z suffix
        if date_string.endswith('Z'):
            date_string = date_string[:-1] + '+00:00'

        dt = datetime.fromisoformat(date_string)
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        return None
