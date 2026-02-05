"""
Data fetcher module for Polymarket API
Handles all API calls with retry logic and rate limiting
"""

import time
import json
from typing import List, Dict, Optional, Any
from urllib import request, error, parse

import config
from evaluator.utils import validate_address


class PolymarketAPIError(Exception):
    """Custom exception for Polymarket API errors"""
    pass


class DataFetcher:
    """Fetches data from Polymarket APIs"""

    def __init__(self):
        self.data_api_base = config.API_ENDPOINTS['data_api']
        self.gamma_api_base = config.API_ENDPOINTS['gamma_api']
        self.timeout = config.REQUEST_SETTINGS['timeout']
        self.max_retries = config.REQUEST_SETTINGS['max_retries']
        self.retry_delay = config.REQUEST_SETTINGS['retry_delay']
        self.rate_limit_delay = config.REQUEST_SETTINGS['rate_limit_delay']

    def _make_request(self, url: str) -> Any:
        """
        Make HTTP GET request with retry logic

        Args:
            url: Full URL to request

        Returns:
            Parsed JSON response

        Raises:
            PolymarketAPIError: If request fails after retries
        """
        for attempt in range(self.max_retries):
            try:
                req = request.Request(url, headers={'User-Agent': 'PMBot/1.0'})
                with request.urlopen(req, timeout=self.timeout) as response:
                    data = response.read()
                    return json.loads(data)
            except error.HTTPError as e:
                if e.code == 401:
                    raise PolymarketAPIError(f"Unauthorized: {url}")
                elif e.code == 400:
                    raise PolymarketAPIError(f"Bad request: {url}")
                elif attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    raise PolymarketAPIError(f"HTTP {e.code} after {self.max_retries} retries: {url}")
            except error.URLError as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    raise PolymarketAPIError(f"Connection error after {self.max_retries} retries: {e}")
            except Exception as e:
                raise PolymarketAPIError(f"Unexpected error: {e}")

        raise PolymarketAPIError(f"Failed after {self.max_retries} retries")

    def _paginate_request(self, base_url: str, limit: int, params: Dict[str, str]) -> List[Dict]:
        """
        Handle paginated API requests

        Args:
            base_url: Base URL for the endpoint
            limit: Results per page
            params: Query parameters

        Returns:
            List of all results across all pages
        """
        all_results = []
        offset = 0

        while offset < config.PAGINATION['max_offset']:
            params['limit'] = str(limit)
            params['offset'] = str(offset)

            query_string = parse.urlencode(params)
            url = f"{base_url}?{query_string}"

            results = self._make_request(url)

            if not results or len(results) == 0:
                break

            all_results.extend(results)

            if len(results) < limit:
                break

            offset += limit
            time.sleep(self.rate_limit_delay)

        return all_results

    def fetch_user_trades(self, user_address: str) -> List[Dict]:
        """
        Fetch all trades for a user

        Args:
            user_address: Ethereum wallet address

        Returns:
            List of trade objects

        Raises:
            PolymarketAPIError: If request fails
        """
        if not validate_address(user_address):
            raise ValueError(f"Invalid address format: {user_address}")

        base_url = f"{self.data_api_base}/trades"
        params = {'user': user_address}

        trades = self._paginate_request(
            base_url,
            config.PAGINATION['trades_limit'],
            params
        )

        return trades

    def fetch_closed_positions(self, user_address: str) -> List[Dict]:
        """
        Fetch all closed positions for a user

        Args:
            user_address: Ethereum wallet address

        Returns:
            List of closed position objects

        Raises:
            PolymarketAPIError: If request fails
        """
        if not validate_address(user_address):
            raise ValueError(f"Invalid address format: {user_address}")

        base_url = f"{self.data_api_base}/closed-positions"
        params = {
            'user': user_address,
            'sortBy': 'TIMESTAMP',
            'sortDirection': 'DESC'
        }

        positions = self._paginate_request(
            base_url,
            config.PAGINATION['positions_limit'],
            params
        )

        return positions

    def fetch_current_positions(self, user_address: str) -> List[Dict]:
        """
        Fetch current open positions for a user

        Args:
            user_address: Ethereum wallet address

        Returns:
            List of current position objects

        Raises:
            PolymarketAPIError: If request fails
        """
        if not validate_address(user_address):
            raise ValueError(f"Invalid address format: {user_address}")

        base_url = f"{self.data_api_base}/positions"
        params = {'user': user_address}

        positions = self._paginate_request(
            base_url,
            config.PAGINATION['positions_limit'],
            params
        )

        return positions

    def fetch_all_tags(self) -> List[Dict]:
        """
        Fetch all available market tags/categories

        Returns:
            List of tag objects

        Raises:
            PolymarketAPIError: If request fails
        """
        url = f"{self.gamma_api_base}/tags"
        tags = self._make_request(url)
        time.sleep(self.rate_limit_delay)
        return tags

    def fetch_market_by_condition_id(self, condition_id: str) -> Optional[Dict]:
        """
        Fetch market details by condition ID

        Args:
            condition_id: Market condition ID

        Returns:
            Market object or None if not found

        Raises:
            PolymarketAPIError: If request fails
        """
        try:
            params = parse.urlencode({'id': condition_id})
            url = f"{self.gamma_api_base}/markets?{params}"
            markets = self._make_request(url)
            time.sleep(self.rate_limit_delay)

            if markets and len(markets) > 0:
                return markets[0]
            return None
        except PolymarketAPIError:
            return None
