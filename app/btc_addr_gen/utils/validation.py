"""
Validation utilities for Bitcoin address generator.
"""

import base58

from ..core.key_types import detect_key_type

import logging
logger = logging.getLogger(__name__)

def is_valid_extended_key(key: str) -> bool:
    """
    Check if a string is a valid extended public key.

    Args:
        key: The extended key to validate

    Returns:
        True if the key is valid, False otherwise
    """
    # Check if the key type is supported
    key_type = detect_key_type(key)
    if not key_type:
        return False

    # Try to decode the base58 key
    try:
        decoded = base58.b58decode_check(key)

        # Check the length (4 + 1 + 4 + 4 + 32 + 33 = 78 bytes)
        if len(decoded) != 78:
            return False

        # Check the key format (should start with 0x02 or 0x03 for compressed public keys)
        if decoded[45] not in (2, 3):
            return False

        return True
    except Exception:
        return False
