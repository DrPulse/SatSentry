"""
Address monitoring service for SatSentry.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

from app.btc_addr_gen.utils.validation import is_valid_extended_key
from app.btc_addr_gen.core.key_types import detect_key_type

from app.services import extended_key_manager, mempool_api
from app.services.settings import get_settings, get_file_path, DEFAULT_SETTINGS

logger = logging.getLogger(__name__)

def _ensure_data_files_exist():
    """Ensure data files exist."""
    data_dir = get_file_path('data_dir')
    os.makedirs(data_dir, exist_ok=True)

    single_addresses_file = get_file_path('single_addresses_file')
    if not os.path.exists(single_addresses_file):
        with open(single_addresses_file, 'w') as f:
            json.dump({}, f, indent=4)

    extended_keys_file = get_file_path('extended_keys_file')
    if not os.path.exists(extended_keys_file):
        with open(extended_keys_file, 'w') as f:
            json.dump({}, f, indent=4)

def _load_single_addresses() -> Dict[str, Any]:
    """Load single addresses from file."""
    _ensure_data_files_exist()

    try:
        single_addresses_file = get_file_path('single_addresses_file')
        with open(single_addresses_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading single addresses: {e}")
        return {}

def _save_single_addresses(addresses: Dict[str, Any]) -> None:
    """Save single addresses to file."""
    _ensure_data_files_exist()

    try:
        single_addresses_file = get_file_path('single_addresses_file')
        with open(single_addresses_file, 'w') as f:
            json.dump(addresses, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving single addresses: {e}")
        raise ValueError(f"Failed to save addresses: {e}")

def _load_extended_keys() -> Dict[str, Any]:
    """Load extended public keys from file."""
    _ensure_data_files_exist()

    try:
        extended_keys_file = get_file_path('extended_keys_file')
        with open(extended_keys_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading extended keys: {e}")
        return {}

def _save_extended_keys(keys: Dict[str, Any]) -> None:
    """Save extended public keys to file."""
    _ensure_data_files_exist()

    try:
        extended_keys_file = get_file_path('extended_keys_file')
        with open(extended_keys_file, 'w') as f:
            json.dump(keys, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving extended keys: {e}")
        raise ValueError(f"Failed to save extended keys: {e}")

def is_valid_bitcoin_address(address: str) -> bool:
    """
    Validate a Bitcoin address.

    Args:
        address: The Bitcoin address to validate

    Returns:
        True if the address is valid, False otherwise
    """
    # Simple validation for now - could be improved
    if address.startswith('1') and len(address) >= 26 and len(address) <= 34:
        return True  # Legacy address
    elif address.startswith('3') and len(address) >= 26 and len(address) <= 34:
        return True  # P2SH address
    elif address.startswith('bc1') and len(address) >= 42 and len(address) <= 62:
        return True  # Bech32 address
    return False

def add_single_address(address: str, label: str = '') -> None:
    """
    Add a single Bitcoin address for monitoring.

    Args:
        address: The Bitcoin address to monitor
        label: Optional label for the address

    Raises:
        ValueError: If the address is invalid or already exists
    """
    if not is_valid_bitcoin_address(address):
        raise ValueError("Invalid Bitcoin address")

    addresses = _load_single_addresses()

    if address in addresses:
        raise ValueError("Address already exists")

    addresses[address] = {
        'label': label,
        'added_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'last_tx': None
    }

    _save_single_addresses(addresses)
    logger.info(f"Added single address: {address}")

def add_extended_public_key(
    extended_key: str,
    gap_limit: int = DEFAULT_SETTINGS['gap'],
    initial_addresses: int = DEFAULT_SETTINGS['initial_addresses'],
    label: str = '',
    derivation_path: str = '',
    start_index: int = 0,
) -> None:
    """
    Add an extended public key for monitoring.

    Args:
        extended_key: The extended public key (xpub/ypub/zpub)
        label: Optional label for the key
        derivation_path: Custom derivation path
        start_index: Starting index for address derivation
        gap_limit: Gap limit for address derivation
        initial_addresses: Initial number of addresses to generate (defaults to global setting)

    Raises:
        ValueError: If the key is invalid or the derivation path already exists
    """
    # Set default derivation path based on key type if not provided
    if not derivation_path:
        # Detect key type first to determine default path
        if not is_valid_extended_key(extended_key):
            raise ValueError("Invalid extended public key")

        key_type = detect_key_type(extended_key)
        if not key_type:
            raise ValueError("Unsupported extended key format")

        if key_type.name == 'XPUB':
            derivation_path = "m/44'/0'/0'"
        elif key_type.name == 'YPUB':
            derivation_path = "m/49'/0'/0'"
        elif key_type.name == 'ZPUB':
            derivation_path = "m/84'/0'/0'"

    # Get settings for initial address count if not provided
    if initial_addresses is None:
        settings = get_settings()
        initial_addresses = settings.get('initial_addresses', DEFAULT_SETTINGS['initial_addresses'])


    # Use the extended key manager to add the key
    extended_key_manager.add_extended_key(
        extended_key=extended_key,
        gap_limit=gap_limit,
        label=label,
        derivation_path=derivation_path,
        start_index=start_index,
        initial_addresses=initial_addresses,
    )

    # Set the added date (handled separately in the manager)
    keys = _load_extended_keys()
    if extended_key in keys:
        keys[extended_key]['added_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        _save_extended_keys(keys)

    logger.info(f"Added extended key: {extended_key[:8]}... with derivation path {derivation_path}")

def get_all_addresses() -> Dict[str, Any]:
    """
    Get all monitored single addresses.

    Returns:
        Dictionary of addresses with their metadata
    """
    return _load_single_addresses()

def get_all_extended_keys() -> Dict[str, Any]:
    """
    Get all monitored extended public keys.

    Returns:
        Dictionary of extended keys with their metadata
    """
    return _load_extended_keys()

def delete_address(address: str) -> None:
    """
    Delete a monitored address.

    Args:
        address: The address to delete

    Raises:
        ValueError: If the address doesn't exist
    """
    addresses = _load_single_addresses()

    if address not in addresses:
        raise ValueError("Address not found")

    del addresses[address]
    _save_single_addresses(addresses)
    logger.info(f"Deleted address: {address}")

def delete_extended_key(extended_key: str) -> None:
    """
    Delete a monitored extended public key and all its derivation paths.

    Args:
        extended_key: The extended key to delete

    Raises:
        ValueError: If the extended key doesn't exist
    """
    keys = _load_extended_keys()

    if extended_key not in keys:
        raise ValueError("Extended key not found")

    del keys[extended_key]
    _save_extended_keys(keys)
    logger.info(f"Deleted extended key: {extended_key[:8]}...")

def delete_extended_key_derivation_path(extended_key: str, derivation_path: str) -> None:
    """
    Delete a specific derivation path for an extended key.

    Args:
        extended_key: The extended key
        derivation_path: The derivation path to delete

    Raises:
        ValueError: If the key or derivation path doesn't exist
    """
    keys = _load_extended_keys()

    if extended_key not in keys:
        raise ValueError("Extended key not found")

    if derivation_path not in keys[extended_key].get('derivation_paths', {}):
        raise ValueError("Derivation path not found for this extended key")

    # Delete the derivation path
    del keys[extended_key]['derivation_paths'][derivation_path]

    # If no derivation paths remain, delete the entire extended key
    if not keys[extended_key]['derivation_paths']:
        del keys[extended_key]

    _save_extended_keys(keys)
    logger.info(f"Deleted derivation path {derivation_path} for extended key: {extended_key[:8]}...")

def refresh_address(address: str) -> Dict[str, Any]:
    """
    Manually refresh an address to check for new transactions.

    Args:
        address: The address to refresh

    Returns:
        Dictionary with refresh results

    Raises:
        ValueError: If the address doesn't exist or the refresh fails
    """
    # Check if it's a single address
    single_addresses = _load_single_addresses()
    if address in single_addresses:
        return _check_single_address(address, single_addresses[address])

    # Check if it's a derived address
    extended_keys = _load_extended_keys()
    for extended_key, key_data in extended_keys.items():
        for deriv_path, path_data in key_data.get('derivation_paths', {}).items():
            for addr_path, addr_data in path_data.get('derived_addresses', {}).items():
                if isinstance(addr_data, dict):
                    addr = addr_data.get('address')
                    if addr == address:
                        # Include the actual transaction history in the metadata
                        metadata = {
                            'label': f"{key_data.get('label', '')} ({addr_path})",
                            'last_tx': addr_data.get('last_tx')
                        }
                        return _check_single_address(address, metadata)
                else:  # Old format - string address
                    if addr_data == address:
                        return _check_single_address(address, {'label': f"{key_data.get('label', '')} ({addr_path})"})

    raise ValueError("Address not found")

def _check_single_address(address: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check a single address for new transactions.

    Args:
        address: The address to check
        metadata: The address metadata

    Returns:
        Dictionary with check results
    """
    try:
        # Get transactions for the address
        transactions = mempool_api.get_address_transactions(address)

        if not transactions:
            return {
                'address': address,
                'label': metadata.get('label', ''),
                'new_transactions': False,
                'message': 'No transactions found',
                'transactions': []
            }

        # Get the latest transaction
        latest_tx = transactions[0]
        latest_txid = latest_tx.get('txid')

        # Get transaction details to access block_time timestamp
        tx_details = mempool_api.get_transaction_details(latest_txid)

        # Use block_time timestamp from mempool API if available
        if 'status' in tx_details and tx_details['status'].get('confirmed', False) and 'block_time' in tx_details['status']:
            # Convert block_time (Unix timestamp) to a human-readable format
            tx_timestamp = datetime.fromtimestamp(tx_details['status']['block_time']).isoformat()
        else:
            # If transaction is not confirmed yet, use current time
            tx_timestamp = datetime.now().isoformat()

        # Determine transaction direction
        direction = _determine_tx_direction(address, latest_tx)

        # Create transaction info
        tx_info = {
            'txid': latest_txid,
            'direction': direction,
            'timestamp': tx_timestamp
        }

        # Check if this is a new transaction
        last_tx = metadata.get('last_tx')
        is_new = False

        if not last_tx or last_tx.get('txid') != latest_txid:
            is_new = True

            # Update the last transaction in metadata
            metadata['last_tx'] = tx_info

            # Save the updated metadata
            addresses = _load_single_addresses()
            if address in addresses:
                addresses[address] = metadata
                _save_single_addresses(addresses)
        else:
            # Even if it's not a new transaction, update the timestamp to use block_time
            if last_tx and last_tx.get('txid') == latest_txid and last_tx.get('timestamp') != tx_timestamp:
                metadata['last_tx']['timestamp'] = tx_timestamp
                addresses = _load_single_addresses()
                if address in addresses:
                    addresses[address] = metadata
                    _save_single_addresses(addresses)

        # Always update the address status and transaction info for extended key addresses
        # This ensures the timestamp is updated even for existing transactions
        extended_key_manager.update_address_used_status(address, True, tx_info)

        return {
            'address': address,
            'label': metadata.get('label', ''),
            'new_transactions': is_new,
            'latest_tx': latest_tx,
            'message': 'New transaction found' if is_new else 'No new transactions'
        }

    except Exception as e:
        logger.error(f"Error checking address {address}: {e}")
        return {
            'address': address,
            'label': metadata.get('label', ''),
            'error': str(e),
            'message': f'Error checking address: {e}'
        }

def _determine_tx_direction(address: str, tx: Dict[str, Any]) -> str:
    """
    Determine the direction of a transaction (incoming or outgoing).

    Args:
        address: The address to check
        tx: The transaction data

    Returns:
        'incoming' or 'outgoing'
    """
    # Check inputs for the address
    for vin in tx.get('vin', []):
        if vin.get('prevout', {}).get('scriptpubkey_address') == address:
            return 'outgoing'

    # If not in inputs, it must be incoming
    return 'incoming'

def check_all_addresses() -> List[Dict[str, Any]]:
    """
    Check all monitored addresses for new transactions.

    Returns:
        List of check results for addresses with new transactions
    """
    results = []

    # Check single addresses
    single_addresses = _load_single_addresses()
    for address, metadata in single_addresses.items():
        result = _check_single_address(address, metadata)
        if result.get('new_transactions'):
            results.append(result)

    # Check derived addresses
    extended_keys = _load_extended_keys()
    for extended_key, key_data in extended_keys.items():
        for deriv_path, path_data in key_data.get('derivation_paths', {}).items():
            for addr_path, addr_data in path_data.get('derived_addresses', {}).items():
                if isinstance(addr_data, dict):
                    address = addr_data.get('address')
                    # Include the actual transaction history in the metadata
                    metadata = {
                        'label': f"{key_data.get('label', '')} ({addr_path})",
                        'last_tx': addr_data.get('last_tx')
                    }
                else:  # Old format - string address
                    address = addr_data
                    metadata = {'label': f"{key_data.get('label', '')} ({addr_path})"}

                result = _check_single_address(address, metadata)
                if result.get('new_transactions'):
                    results.append(result)

            # Ensure gap limit after checking addresses for this derivation path
            extended_key_manager.ensure_gap_limit(extended_key, deriv_path)

    return results
