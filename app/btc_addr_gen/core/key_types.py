"""
Key types and format definitions for Bitcoin extended keys.
"""
from enum import Enum, auto
from typing import Dict, Optional


class KeyType(Enum):
    """Types of extended keys."""
    XPUB = auto()  # Standard BIP32 extended public key (Legacy)
    YPUB = auto()  # BIP49 extended public key (P2SH-wrapped SegWit)
    ZPUB = auto()  # BIP84 extended public key (Native SegWit)


class AddressType(Enum):
    """Types of Bitcoin addresses."""
    P2PKH = auto()      # Legacy addresses (1...)
    P2SH_P2WPKH = auto() # P2SH-wrapped SegWit addresses (3...)
    P2WPKH = auto()     # Native SegWit addresses (bc1q...)


# Mapping from key type to derivation path purpose
KEY_TYPE_TO_PURPOSE: Dict[KeyType, int] = {
    KeyType.XPUB: 44,  # BIP44 (Legacy)
    KeyType.YPUB: 49,  # BIP49 (P2SH-wrapped SegWit)
    KeyType.ZPUB: 84,  # BIP84 (Native SegWit)
}


# Mapping from key type to address type
KEY_TO_ADDRESS_TYPE: Dict[KeyType, AddressType] = {
    KeyType.XPUB: AddressType.P2PKH,
    KeyType.YPUB: AddressType.P2SH_P2WPKH,
    KeyType.ZPUB: AddressType.P2WPKH,
}


def detect_key_type(extended_key: str) -> Optional[KeyType]:
    """
    Detect the type of extended key based on its prefix.

    Args:
        extended_key: The extended key string

    Returns:
        KeyType or None if the key type couldn't be determined
    """
    prefix = extended_key[:4].lower()

    if prefix == "xpub":
        return KeyType.XPUB
    elif prefix == "ypub":
        return KeyType.YPUB
    elif prefix == "zpub":
        return KeyType.ZPUB

    return None
