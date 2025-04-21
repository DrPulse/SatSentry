"""
Core functionality for Bitcoin address generation.
Contains the main address generation logic and key type definitions.
"""

from .address_generator import AddressGenerator
from .key_types import KeyType, AddressType, detect_key_type

__all__ = [
    'AddressGenerator',
    'KeyType',
    'AddressType',
    'detect_key_type',
]
