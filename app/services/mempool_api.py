"""
Mempool.space API integration for SatSentry.
"""

import logging
import requests
from typing import Dict, Any, List

from app.services.settings import get_settings, DEFAULT_SETTINGS

logger = logging.getLogger(__name__)

def get_api_url() -> str:
    """Get the API URL based on settings."""
    settings = get_settings()

    if settings.get('use_self_hosted', False):
        protocol = 'https' if settings.get('node_port') == 443 else 'http'
        return f"{protocol}://{settings.get('node_url')}:{settings.get('node_port')}/api"
    else:
        return f"{DEFAULT_SETTINGS['node_url']}/api"

def get_address_transactions(address: str) -> List[Dict[str, Any]]:
    """
    Get transactions for a Bitcoin address.

    Args:
        address: The Bitcoin address to check

    Returns:
        List of transactions for the address

    Raises:
        ValueError: If the API request fails
    """
    api_url = get_api_url()
    endpoint = f"{api_url}/address/{address}/txs"

    try:
        response = requests.get(endpoint, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching transactions for address {address}: {e}")
        raise ValueError(f"Failed to fetch transactions: {e}")

def get_transaction_details(txid: str) -> Dict[str, Any]:
    """
    Get details for a specific transaction.

    Args:
        txid: The transaction ID

    Returns:
        Transaction details

    Raises:
        ValueError: If the API request fails
    """
    api_url = get_api_url()
    endpoint = f"{api_url}/tx/{txid}"

    try:
        response = requests.get(endpoint, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching transaction details for txid {txid}: {e}")
        raise ValueError(f"Failed to fetch transaction details: {e}")

def get_fee_estimates() -> Dict[str, int]:
    """
    Get current fee estimates.

    Returns:
        Dictionary of fee estimates for different confirmation targets

    Raises:
        ValueError: If the API request fails
    """
    api_url = get_api_url()
    endpoint = f"{api_url}/v1/fees/recommended"

    try:
        response = requests.get(endpoint, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching fee estimates: {e}")
        raise ValueError(f"Failed to fetch fee estimates: {e}")


def test_api_connection() -> bool:
    """
    Test the connection to the mempool API.

    Returns:
        True if the connection is successful, False otherwise
    """
    api_url = get_api_url()
    endpoint = f"{api_url}/blocks/tip/height"
    try:
        response = requests.get(endpoint, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"API connection test failed: {e}")
        return False
