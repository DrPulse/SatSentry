"""
Extended key management service for SatSentry.

This module handles the management of extended public keys, including:
- Address derivation
- Gap limit maintenance
- Transaction status tracking
"""

import os
import json
import logging
from typing import Dict, Any, Optional

from app.btc_addr_gen.core.address_generator import AddressGenerator
from app.btc_addr_gen.utils.validation import is_valid_extended_key
from app.btc_addr_gen.core.key_types import detect_key_type

from app.services import mempool_api
from app.services.settings import get_file_path, DEFAULT_SETTINGS

def _ensure_data_files_exist():
    """Ensure data files exist."""
    data_dir = get_file_path('data_dir')
    os.makedirs(data_dir, exist_ok=True)

    extended_keys_file = get_file_path('extended_keys_file')
    if not os.path.exists(extended_keys_file):
        with open(extended_keys_file, 'w') as f:
            json.dump({}, f, indent=4)

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

logger = logging.getLogger(__name__)


# TODO: find a better way to dynamically generate new addresses and check them instead of raw double loop w/ ensure_gap_limit function
def add_extended_key(
    extended_key: str,
    gap_limit: int = DEFAULT_SETTINGS['gap'],
    label: str = '',
    derivation_path: str = '',
    start_index: int = 0,
    initial_addresses: int = DEFAULT_SETTINGS['initial_addresses'],
) -> Dict[str, Any]:
    """
    Add an extended public key for monitoring.

    Args:
        extended_key: The extended public key (xpub/ypub/zpub)
        label: Optional label for the key
        derivation_path: Custom derivation path
        start_index: Starting index for address derivation
        initial_addresses: Initial number of addresses to generate
        gap_limit: Gap limit for address derivation (stored per key)

    Returns:
        The added key data

    Raises:
        ValueError: If the key is invalid or the derivation path already exists
    """
    if not is_valid_extended_key(extended_key):
        raise ValueError("Invalid extended public key")

    # Detect key type
    key_type = detect_key_type(extended_key)
    if not key_type:
        raise ValueError("Unsupported extended key format")

    # Load existing keys
    keys = _load_extended_keys()

    # Check if this extended key exists
    if extended_key in keys:
        # Check if this derivation path already exists for this key
        if derivation_path in keys[extended_key].get('derivation_paths', {}):
            raise ValueError("This derivation path already exists for this extended key")

        # Use existing label if not provided
        if not label:
            label = keys[extended_key].get('label', '')
    else:
        # Create new entry for this extended key
        keys[extended_key] = {
            'label': label,
            'key_type': key_type.name,
            'added_date': None,  # Will be set by address_monitor
            'derivation_paths': {}
        }

    # Generate initial addresses
    generator = AddressGenerator(extended_key)
    addresses = generator.generate_addresses(start_index, initial_addresses)


    # Format addresses for storage
    derived_addresses = {}
    for idx, addr in addresses:
        path = f"{derivation_path}/0/{idx}" if derivation_path else f"0/{idx}"
        derived_addresses[path] = {
            'address': addr,
            'used': False,
            'last_tx': None
        }

    # Add the derivation path to the extended key
    if 'derivation_paths' not in keys[extended_key]:
        keys[extended_key]['derivation_paths'] = {}

    keys[extended_key]['derivation_paths'][derivation_path] = {
        'start_index': start_index,
        'current_index': start_index + initial_addresses - 1,
        'gap_limit': gap_limit,  # Store gap limit per key/path
        'derived_addresses': derived_addresses
    }

    # Save the updated keys
    _save_extended_keys(keys)

    # Check initial addresses for transactions
    logger.info(f"Checking {initial_addresses} initial addresses for transactions")
    newly_generated_addresses = [addr for _, addr in addresses]

    try:
        # Import at function level to avoid circular imports
        from app.services.address_monitor import _check_single_address

        # Track if any addresses were found to be used
        any_used_addresses = False
        path_data = keys[extended_key]['derivation_paths'][derivation_path]

        # Check each new address for transactions
        for i, addr in enumerate(newly_generated_addresses):
            try:
                # Create path for this address
                idx = start_index + i
                addr_path = f"{derivation_path}/0/{idx}" if derivation_path else f"0/{idx}"

                # Create metadata for the address
                metadata = {
                    'label': f"{keys[extended_key].get('label', '')} ({addr_path})",
                    'last_tx': None
                }

                # Check the address for transactions
                result = _check_single_address(addr, metadata)

                # If transactions were found, update the in-memory data structure
                if result.get('new_transactions', False):
                    logger.info(f"Found transactions for initial address {addr}")
                    path_data['derived_addresses'][addr_path]['used'] = True
                    path_data['derived_addresses'][addr_path]['last_tx'] = metadata.get('last_tx')
                    any_used_addresses = True
            except Exception as e:
                logger.error(f"Error checking initial address {addr}: {e}")

        # If any addresses were found to be used, we need to ensure the gap limit
        if any_used_addresses:
            logger.info("Ensuring gap limit after finding used addresses in initial set")

            # Recalculate consecutive empty addresses
            paths = sorted(path_data['derived_addresses'].keys(), key=lambda p: int(p.split('/')[-1]))
            last_used_index = -1

            for i, path in enumerate(paths):
                addr_data = path_data['derived_addresses'][path]
                if isinstance(addr_data, dict) and addr_data.get('used', False):
                    last_used_index = i

            consecutive_empty = len(paths) - last_used_index - 1
            gap_limit = path_data.get('gap_limit', DEFAULT_SETTINGS['gap'])

            # If we don't have enough consecutive empty addresses, generate more
            if consecutive_empty < gap_limit:
                additional_needed = gap_limit - consecutive_empty
                current_index = path_data['current_index']
                new_start_index = current_index + 1

                logger.info(f"Need {additional_needed} more addresses to maintain gap limit")

                # Generate additional addresses
                generator = AddressGenerator(extended_key)
                more_addresses = generator.generate_addresses(new_start_index, additional_needed)

                # Add new addresses to derived_addresses
                for idx, addr in more_addresses:
                    path = f"{derivation_path}/0/{idx}" if derivation_path else f"0/{idx}"
                    path_data['derived_addresses'][path] = {
                        'address': addr,
                        'used': False,
                        'last_tx': None
                    }

                # Update current_index
                path_data['current_index'] = new_start_index + additional_needed - 1

                # Save the updated data
                _save_extended_keys(keys)
                logger.info(f"Generated {additional_needed} additional addresses to maintain gap limit")
    except Exception as e:
        logger.error(f"Error checking initial addresses: {e}")

    # Return the added key data
    return keys[extended_key]


def ensure_gap_limit(extended_key: str, derivation_path: str) -> int:
    """
    Ensure that the extended key has at least the configured gap limit of consecutive empty addresses
    for the specified derivation path. If new addresses are generated, they are checked for transactions
    immediately.

    Args:
        extended_key: The extended key
        derivation_path: The derivation path to check

    Returns:
        Number of new addresses generated (0 if gap limit is already satisfied)
    """
    keys = _load_extended_keys()
    if extended_key not in keys or derivation_path not in keys[extended_key].get('derivation_paths', {}):
        logger.warning(f"Cannot ensure gap limit: key or path not found ({extended_key[:8]}.../{derivation_path})")
        return 0

    path_data = keys[extended_key]['derivation_paths'][derivation_path]
    addresses = path_data['derived_addresses']

    # Get the gap limit for this specific key/path
    gap_limit = path_data.get('gap_limit', DEFAULT_SETTINGS['gap'])

    # Count consecutive empty addresses at the end
    paths = sorted(addresses.keys(), key=lambda p: int(p.split('/')[-1]))

    # Find the last used address index
    last_used_index = -1
    for i, path in enumerate(paths):
        addr_data = addresses[path]
        if isinstance(addr_data, dict):
            if addr_data.get('used', False):
                last_used_index = i
        else:
            try:
                transactions = mempool_api.get_address_transactions(addr_data)
                if transactions:
                    last_used_index = i
            except Exception:
                # If we can't check, assume it's unused
                pass

    # Calculate how many consecutive unused addresses we have
    consecutive_empty = len(paths) - last_used_index - 1

    # If we have fewer consecutive empty addresses than the gap limit,
    # generate more addresses
    if consecutive_empty < gap_limit:
        additional_needed = gap_limit - consecutive_empty
        current_index = path_data['current_index']
        start_index = current_index + 1

        # Generate additional addresses
        generator = AddressGenerator(extended_key)
        new_addresses = generator.generate_addresses(start_index, additional_needed)

        # Add new addresses to derived_addresses and check them for transactions
        newly_generated_addresses = []
        for idx, addr in new_addresses:
            path = f"{derivation_path}/0/{idx}" if derivation_path else f"0/{idx}"
            path_data['derived_addresses'][path] = {
                'address': addr,
                'used': False,
                'last_tx': None  # Explicitly set to None for new addresses
            }
            newly_generated_addresses.append(addr)

        # Update current_index
        path_data['current_index'] = start_index + additional_needed - 1

        # Save updated data
        _save_extended_keys(keys)
        logger.info(f"Generated {additional_needed} new addresses for {extended_key[:8]}... with derivation path {derivation_path} to maintain gap limit")

        # Check newly generated addresses for transactions
        if newly_generated_addresses:
            logger.info(f"Checking {len(newly_generated_addresses)} newly generated addresses for transactions")
            # Import at function level to avoid circular imports
            from app.services.address_monitor import _check_single_address

            # Track if any addresses were found to be used
            any_used_addresses = False

            # Check each new address for transactions
            for i, addr in enumerate(newly_generated_addresses):
                try:
                    # Create path for this address
                    idx = start_index + i
                    addr_path = f"{derivation_path}/0/{idx}" if derivation_path else f"0/{idx}"

                    # Create metadata for the address
                    metadata = {
                        'label': f"{keys[extended_key].get('label', '')} ({addr_path})",
                        'last_tx': None
                    }

                    # Check the address for transactions
                    result = _check_single_address(addr, metadata)

                    # If transactions were found, update the in-memory data structure
                    if result.get('new_transactions', False):
                        logger.info(f"Found transactions for newly generated address {addr}")
                        path_data['derived_addresses'][addr_path]['used'] = True
                        path_data['derived_addresses'][addr_path]['last_tx'] = metadata.get('last_tx')
                        any_used_addresses = True
                except Exception as e:
                    logger.error(f"Error checking newly generated address {addr}: {e}")

            # If any addresses were found to be used, we need to recalculate the gap limit
            if any_used_addresses:
                logger.info("Recalculating gap limit after finding used addresses")

                # Recalculate consecutive empty addresses
                paths = sorted(path_data['derived_addresses'].keys(), key=lambda p: int(p.split('/')[-1]))
                last_used_index = -1

                for i, path in enumerate(paths):
                    addr_data = path_data['derived_addresses'][path]
                    if isinstance(addr_data, dict) and addr_data.get('used', False):
                        last_used_index = i

                consecutive_empty = len(paths) - last_used_index - 1

                # If we still don't have enough consecutive empty addresses, generate more
                if consecutive_empty < gap_limit:
                    additional_needed = gap_limit - consecutive_empty
                    current_index = path_data['current_index']
                    new_start_index = current_index + 1

                    logger.info(f"Need {additional_needed} more addresses to maintain gap limit")

                    # Generate additional addresses
                    generator = AddressGenerator(extended_key)
                    more_addresses = generator.generate_addresses(new_start_index, additional_needed)

                    # Add new addresses to derived_addresses
                    for idx, addr in more_addresses:
                        path = f"{derivation_path}/0/{idx}" if derivation_path else f"0/{idx}"
                        path_data['derived_addresses'][path] = {
                            'address': addr,
                            'used': False,
                            'last_tx': None
                        }

                    # Update current_index
                    path_data['current_index'] = new_start_index + additional_needed - 1

                    # Save the updated data
                    _save_extended_keys(keys)
                    logger.info(f"Generated {additional_needed} additional addresses to maintain gap limit")

                    # Note: We don't check these additional addresses immediately to avoid potential
                    # infinite recursion. They will be checked during the next scheduled check.

        return additional_needed

    return 0


def update_address_used_status(address: str, used: bool, transaction_info: Optional[Dict[str, Any]] = None) -> bool:
    """
    Update the used status of an address derived from an extended key.

    Args:
        address: The address to update
        used: Whether the address has been used
        transaction_info: Optional transaction information

    Returns:
        True if the address was found and updated, False otherwise
    """
    extended_keys = _load_extended_keys()
    updated = False

    for _, key_data in extended_keys.items():
        for _, path_data in key_data.get('derivation_paths', {}).items():
            for addr_path, addr_data in path_data.get('derived_addresses', {}).items():
                if isinstance(addr_data, dict) and addr_data.get('address') == address:
                    # Always mark as used if it has transactions
                    addr_data['used'] = used

                    # Update transaction info if it's provided
                    if transaction_info and transaction_info.get('txid'):
                        # Check if this is a new transaction
                        current_tx = addr_data.get('last_tx')
                        if not current_tx or current_tx.get('txid') != transaction_info.get('txid'):
                            # New transaction - update everything
                            addr_data['last_tx'] = transaction_info
                            updated = True
                        elif current_tx and current_tx.get('txid') == transaction_info.get('txid'):
                            # Same transaction - always update the timestamp to ensure it uses block_time
                            # This ensures feature parity between single addresses and extended key addresses
                            if transaction_info.get('timestamp'):
                                current_tx['timestamp'] = transaction_info.get('timestamp')
                                updated = True
                    elif not used:  # If marking as unused, clear transaction info
                        addr_data['last_tx'] = None
                        updated = True
                elif isinstance(addr_data, str) and addr_data == address:
                    # Convert old format to new format
                    path_data['derived_addresses'][addr_path] = {
                        'address': addr_data,
                        'used': used,
                        'last_tx': transaction_info if transaction_info and transaction_info.get('txid') else None
                    }
                    updated = True

    if updated:
        _save_extended_keys(extended_keys)
        return True

    return False


def update_gap_limit(extended_key: str, derivation_path: str, new_gap_limit: int) -> bool:
    """
    Update the gap limit for a specific derivation path.

    Args:
        extended_key: The extended key
        derivation_path: The derivation path to update
        new_gap_limit: The new gap limit value

    Returns:
        True if the gap limit was updated, False otherwise

    Raises:
        ValueError: If the extended key or derivation path doesn't exist, or if the new gap limit is invalid
    """
    if new_gap_limit < 1:
        raise ValueError("Gap limit must be at least 1")

    keys = _load_extended_keys()

    if extended_key not in keys:
        raise ValueError("Extended key not found")

    if derivation_path not in keys[extended_key].get('derivation_paths', {}):
        raise ValueError("Derivation path not found for this extended key")

    path_data = keys[extended_key]['derivation_paths'][derivation_path]
    current_gap_limit = path_data.get('gap_limit', DEFAULT_SETTINGS['gap'])

    # If the gap limit hasn't changed, do nothing
    if current_gap_limit == new_gap_limit:
        return False

    # Update the gap limit
    path_data['gap_limit'] = new_gap_limit

    # Save the updated data
    _save_extended_keys(keys)
    logger.info(f"Updated gap limit for {extended_key[:8]}... with derivation path {derivation_path} from {current_gap_limit} to {new_gap_limit}")

    return True

