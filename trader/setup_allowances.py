#!/usr/bin/env python3
"""
One-time setup script to approve USDC spending for Polymarket contracts
Run this before trading for the first time
"""

import sys
from pathlib import Path
from web3 import Web3

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import trader.config as config

# Polygon RPC
POLYGON_RPC = "https://polygon-rpc.com"

# USDC.e on Polygon (NOT regular USDC!)
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# Polymarket Contracts (need approval)
EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"  # Exchange
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"  # CTF
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"  # Neg Risk Adapter

# ERC20 ABI (approve function)
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]

# ERC1155 ABI (setApprovalForAll function)
ERC1155_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "operator", "type": "address"},
            {"name": "approved", "type": "bool"}
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "type": "function"
    }
]


def setup_allowances():
    """Set up USDC allowances for Polymarket trading"""

    if not config.POLYMARKET_PRIVATE_KEY:
        print("❌ POLYMARKET_PRIVATE_KEY not set in .env")
        sys.exit(1)

    print("\n" + "="*60)
    print("POLYMARKET ALLOWANCE SETUP")
    print("="*60)
    print("This script will approve Polymarket contracts to spend your USDC")
    print("This is a ONE-TIME setup that costs gas (POL/MATIC)")
    print("="*60 + "\n")

    # Connect to Polygon
    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
    if not w3.is_connected():
        print("❌ Failed to connect to Polygon")
        sys.exit(1)

    print("✓ Connected to Polygon")

    # Get account from private key
    account = w3.eth.account.from_key(config.POLYMARKET_PRIVATE_KEY)
    address = account.address
    print(f"✓ Account: {address}")

    # Check POL/MATIC balance for gas
    balance = w3.eth.get_balance(address)
    balance_matic = w3.from_wei(balance, 'ether')
    print(f"✓ POL Balance: {balance_matic} POL")

    if balance_matic < 0.01:
        print("⚠️  Low POL balance! You need POL for gas fees")
        print("   Get some from: https://polygon.technology/gas-token")

    # USDC contract
    usdc = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_ADDRESS),
        abi=ERC20_ABI
    )

    # CTF contract
    ctf = w3.eth.contract(
        address=Web3.to_checksum_address(CTF_ADDRESS),
        abi=ERC1155_ABI
    )

    # Max approval amount
    max_approval = 2**256 - 1

    print("\nSetting approvals...\n")

    # 1. Approve Exchange to spend USDC
    print("1️⃣  Approving Exchange contract for USDC...")
    try:
        tx = usdc.functions.approve(
            Web3.to_checksum_address(EXCHANGE_ADDRESS),
            max_approval
        ).build_transaction({
            'from': address,
            'nonce': w3.eth.get_transaction_count(address),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        print(f"   Transaction: {tx_hash.hex()}")
        print("   Waiting for confirmation...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt['status'] == 1:
            print("   ✅ Success!")
        else:
            print("   ❌ Failed!")

    except Exception as e:
        print(f"   ⚠️  Error: {e}")

    # 2. Approve Neg Risk Adapter to spend USDC
    print("\n2️⃣  Approving Neg Risk Adapter for USDC...")
    try:
        tx = usdc.functions.approve(
            Web3.to_checksum_address(NEG_RISK_ADAPTER),
            max_approval
        ).build_transaction({
            'from': address,
            'nonce': w3.eth.get_transaction_count(address),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        print(f"   Transaction: {tx_hash.hex()}")
        print("   Waiting for confirmation...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt['status'] == 1:
            print("   ✅ Success!")
        else:
            print("   ❌ Failed!")

    except Exception as e:
        print(f"   ⚠️  Error: {e}")

    # 3. Approve Exchange for CTF tokens
    print("\n3️⃣  Approving Exchange for CTF tokens...")
    try:
        tx = ctf.functions.setApprovalForAll(
            Web3.to_checksum_address(EXCHANGE_ADDRESS),
            True
        ).build_transaction({
            'from': address,
            'nonce': w3.eth.get_transaction_count(address),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        print(f"   Transaction: {tx_hash.hex()}")
        print("   Waiting for confirmation...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt['status'] == 1:
            print("   ✅ Success!")
        else:
            print("   ❌ Failed!")

    except Exception as e:
        print(f"   ⚠️  Error: {e}")

    # 4. Approve Neg Risk Adapter for CTF tokens
    print("\n4️⃣  Approving Neg Risk Adapter for CTF tokens...")
    try:
        tx = ctf.functions.setApprovalForAll(
            Web3.to_checksum_address(NEG_RISK_ADAPTER),
            True
        ).build_transaction({
            'from': address,
            'nonce': w3.eth.get_transaction_count(address),
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        print(f"   Transaction: {tx_hash.hex()}")
        print("   Waiting for confirmation...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt['status'] == 1:
            print("   ✅ Success!")
        else:
            print("   ❌ Failed!")

    except Exception as e:
        print(f"   ⚠️  Error: {e}")

    print("\n" + "="*60)
    print("✅ ALLOWANCE SETUP COMPLETE!")
    print("="*60)
    print("You can now trade on Polymarket with the bot")
    print("="*60 + "\n")


if __name__ == "__main__":
    setup_allowances()
