"""
Wallet balance tracker for Polymarket (USDC on Polygon)
"""

import requests
from typing import Optional
from web3 import Web3

import trader.config as config


class WalletTracker:
    """Track wallet balances on Polygon"""

    # USDC contract on Polygon
    USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    USDC_DECIMALS = 6

    # Polygon RPC endpoints
    POLYGON_RPC = "https://polygon-rpc.com"

    # Cache for proxy wallet lookups
    _proxy_cache = {}

    # ERC20 ABI (balanceOf function)
    ERC20_ABI = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        }
    ]

    def __init__(self):
        """Initialize Web3 connection"""
        self.w3 = Web3(Web3.HTTPProvider(self.POLYGON_RPC))
        self.usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.USDC_ADDRESS),
            abi=self.ERC20_ABI
        )

    def get_usdc_balance(self, address: str) -> Optional[float]:
        """
        Get USDC balance for a wallet address

        Args:
            address: Ethereum address

        Returns:
            USDC balance as float, or None on error
        """
        try:
            checksum_address = Web3.to_checksum_address(address)
            balance_wei = self.usdc_contract.functions.balanceOf(checksum_address).call()
            balance_usdc = balance_wei / (10 ** self.USDC_DECIMALS)
            return balance_usdc
        except Exception as e:
            print(f"Error fetching USDC balance: {e}")
            return None

    def get_polymarket_positions_value(self, address: str) -> Optional[float]:
        """
        Get total value of open Polymarket positions

        Args:
            address: Ethereum address

        Returns:
            Total position value in USD, or None on error
        """
        try:
            url = f"{config.POLYMARKET_DATA_API}/positions"
            params = {'user': address.lower(), 'limit': 100}
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()

            positions = response.json()
            total_value = sum(float(pos.get('currentValue', 0)) for pos in positions)
            return total_value

        except Exception as e:
            print(f"Error fetching positions value: {e}")
            return None

    def get_polymarket_realized_pnl(self, address: str) -> Optional[float]:
        """
        Get total realized PnL from closed positions

        Args:
            address: Ethereum address

        Returns:
            Total realized PnL in USD, or None on error
        """
        try:
            url = f"{config.POLYMARKET_DATA_API}/closed-positions"
            params = {'user': address.lower(), 'limit': 100}
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()

            closed_positions = response.json()
            realized_pnl = sum(float(pos.get('realizedPnl', 0)) for pos in closed_positions)
            return realized_pnl

        except Exception as e:
            print(f"Error fetching realized PnL: {e}")
            return None

    def calculate_total_net_worth(self, address: str) -> Optional[float]:
        """
        Calculate total net worth: USDC balance + position value

        Args:
            address: Ethereum address

        Returns:
            Total net worth in USD, or None on error
        """
        usdc_balance = self.get_usdc_balance(address)
        positions_value = self.get_polymarket_positions_value(address)

        if usdc_balance is None or positions_value is None:
            return None

        return usdc_balance + positions_value

    def find_proxy_wallet(self, eoa_address: str) -> Optional[str]:
        """
        Find Polymarket proxy wallet address for an EOA

        Args:
            eoa_address: EOA (main wallet) address

        Returns:
            Proxy wallet address if found, None otherwise
        """
        # Check cache first
        if eoa_address in self._proxy_cache:
            return self._proxy_cache[eoa_address]

        try:
            # Query Polymarket Data API for any activity from this address
            # The proxyWallet field in responses will show the proxy address
            url = f"{config.POLYMARKET_DATA_API}/activity"
            params = {'user': eoa_address.lower(), 'limit': 1}
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()

            data = response.json()
            if data and len(data) > 0:
                proxy = data[0].get('proxyWallet')
                if proxy:
                    self._proxy_cache[eoa_address] = proxy
                    return proxy

            # Try checking positions
            url = f"{config.POLYMARKET_DATA_API}/positions"
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()

            positions = response.json()
            if positions and len(positions) > 0:
                proxy = positions[0].get('proxyWallet')
                if proxy:
                    self._proxy_cache[eoa_address] = proxy
                    return proxy

            return None

        except Exception as e:
            print(f"Error finding proxy wallet: {e}")
            return None

    def get_wallet_summary(self, address: str, try_find_proxy: bool = True) -> dict:
        """
        Get comprehensive wallet summary

        Args:
            address: Ethereum address (EOA or proxy)
            try_find_proxy: If True and address has no activity, try to find associated proxy

        Returns:
            Dictionary with all wallet metrics
        """
        usdc_balance = self.get_usdc_balance(address)
        positions_value = self.get_polymarket_positions_value(address)
        realized_pnl = self.get_polymarket_realized_pnl(address)

        proxy_address = None

        # If no positions found and try_find_proxy enabled, look for proxy wallet
        if try_find_proxy and (positions_value is None or positions_value == 0):
            proxy_address = self.find_proxy_wallet(address)
            if proxy_address and proxy_address.lower() != address.lower():
                # Found a proxy, get its balances instead
                print(f"  ℹ️  Found proxy wallet: {proxy_address}")
                usdc_balance_proxy = self.get_usdc_balance(proxy_address)
                positions_value = self.get_polymarket_positions_value(proxy_address)
                realized_pnl = self.get_polymarket_realized_pnl(proxy_address)

                # Combine EOA balance with proxy positions
                if usdc_balance_proxy is not None:
                    usdc_balance = (usdc_balance or 0) + usdc_balance_proxy

        total_net_worth = None
        if usdc_balance is not None and positions_value is not None:
            total_net_worth = usdc_balance + positions_value

        return {
            'address': address,
            'proxy_address': proxy_address,
            'usdc_balance': usdc_balance,
            'positions_value': positions_value,
            'realized_pnl': realized_pnl,
            'total_net_worth': total_net_worth
        }
