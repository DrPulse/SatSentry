"""
Bitcoin address generator from extended public keys.
A simpler implementation that doesn't rely on complex dependencies.
"""

import hashlib
import hmac
import struct
from typing import List, Tuple, Optional

import base58
import bech32
import ecdsa

from .key_types import KeyType, detect_key_type

# Constants for version bytes and script prefixes
P2PKH_VERSION_BYTE = b'\x00'  # Mainnet P2PKH
P2SH_VERSION_BYTE = b'\x05'   # Mainnet P2SH
P2WPKH_SCRIPT_PREFIX = b'\x00\x14'  # Witness version 0 + push 20 bytes

class AddressGenerator:
    """
    Generator for Bitcoin addresses from extended public keys.
    """

    # BIP32 constants
    BITCOIN_MAINNET_PUBLIC = bytes.fromhex('0488b21e')  # xpub
    BITCOIN_MAINNET_PRIVATE = bytes.fromhex('0488ade4')  # xprv

    # BIP49 constants (P2SH-wrapped SegWit)
    BITCOIN_YPUB = bytes.fromhex('049d7cb2')  # ypub

    # BIP84 constants (Native SegWit)
    BITCOIN_ZPUB = bytes.fromhex('04b24746')  # zpub

    def __init__(
        self, extended_key: str):
        """
        Initialize the address generator.

        Args:
            extended_key: The extended public key (xpub, ypub, or zpub)

        Raises:
            ValueError: If the extended key is invalid or unsupported
        """
        # Detect key type
        self.key_type = detect_key_type(extended_key)
        if not self.key_type:
            raise ValueError(f"Unsupported extended key format: {extended_key[:4]}")

        # Store the original extended key
        self.extended_key = extended_key

        # Parse the extended key
        try:
            self._parse_extended_key()
        except Exception:
            raise ValueError("Invalid extended public key format")

    def _parse_extended_key(self):
        """
        Parse the extended key into its components.
        """
        # Decode the base58 key
        decoded = base58.b58decode_check(self.extended_key)

        # Extract the components
        self.version = decoded[:4]
        self.depth = decoded[4]
        self.parent_fingerprint = decoded[5:9]
        self.child_number = int.from_bytes(decoded[9:13], byteorder='big')
        self.chain_code = decoded[13:45]
        self.key_bytes = decoded[45:]

        # For public keys, the first byte should be 0x02 or 0x03
        if self.key_bytes[0] not in (2, 3):
            raise ValueError("Invalid public key format")

        # Create the public key object
        self.public_key = ecdsa.VerifyingKey.from_string(
            self.key_bytes,
            curve=ecdsa.SECP256k1
        )

    def _derive_child_key(self, index: int, chain_code: Optional[bytes] =None, key_bytes: Optional[bytes] =None, public_key: Optional[ecdsa.VerifyingKey] =None, retry_count: int =0) -> Tuple[bytes, ecdsa.VerifyingKey]:
        """
        Derive a child key at the specified index.

        Args:
            index: The child key index
            chain_code: Optional chain code to use (defaults to self.chain_code)
            key_bytes: Optional key bytes to use (defaults to self.key_bytes)
            public_key: Optional public key to use (defaults to self.public_key)
            retry_count: Internal counter to prevent excessive recursion

        Returns:
            A tuple of (child_chain_code, child_public_key)

        Raises:
            ValueError: If key derivation fails or exceeds maximum retries
        """
        # Use provided values or defaults
        chain_code = chain_code or self.chain_code
        key_bytes = key_bytes or self.key_bytes
        public_key = public_key or self.public_key

        # Add a max retry counter to prevent stack overflow
        MAX_RETRIES = 16  # BIP32 suggests a reasonable limit
        if retry_count >= MAX_RETRIES:
            raise ValueError("Key derivation failed - retry limit exceeded")

        # Create the data to HMAC
        if index >= 0x80000000:
            raise ValueError("Cannot derive hardened keys from a public key")

        data = key_bytes + struct.pack('>L', index)

        # Calculate HMAC-SHA512
        h = hmac.new(chain_code, data, hashlib.sha512).digest()

        # Split into left and right parts
        left, right = h[:32], h[32:]

        # Convert left to a scalar and add to the current key
        left_int = int.from_bytes(left, byteorder='big')

        # Check if left_int is greater than the curve order
        if left_int >= ecdsa.SECP256k1.order:
            return self._derive_child_key(index + 1, chain_code, key_bytes, public_key, retry_count + 1)

        # Add the scalar to the current public key
        point = left_int * ecdsa.SECP256k1.generator

        # Add the new point to the current public key point
        current_point = public_key.pubkey.point
        new_point = current_point + point

        # Convert the new point to a public key
        new_public_key = ecdsa.VerifyingKey.from_public_point(
            new_point,
            curve=ecdsa.SECP256k1
        )

        # Validate that the derived public key is valid
        try:
            # A simple way to check if the key is valid is to verify that we can serialize it
            # This will raise an exception if the key is invalid
            new_public_key.to_string("compressed")
        except Exception:
            # If we encounter any issues during validation, try the next index
            return self._derive_child_key(index + 1, chain_code, key_bytes, public_key, retry_count + 1)

        # Return the new chain code and public key
        return right, new_public_key

    def _derive_path(self, path: str):
        """
        Derive a key from a path.

        Args:
            path: The derivation path (e.g., "0/0")

        Returns:
            The derived public key
        """
        # Start with the current key
        current_chain_code = self.chain_code
        current_key_bytes = self.key_bytes
        current_public_key = self.public_key

        # Split the path and derive each level
        for index_str in path.split('/'):
            if not index_str:
                continue

            # Check for hardened indices
            if index_str.endswith("'") or index_str.endswith("h"):
                raise ValueError("Cannot derive hardened keys from a public key")

            # Convert to integer
            index = int(index_str)

            # Derive the child key
            current_chain_code, current_public_key = self._derive_child_key(
                index,
                current_chain_code,
                current_key_bytes,
                current_public_key
            )

            # Update key bytes for next derivation
            current_key_bytes = current_public_key.to_string("compressed")

        return current_public_key

    def _hash160(self, data: bytes) -> bytes:
        """
        Perform RIPEMD160(SHA256(data)).

        Args:
            data: The data to hash

        Returns:
            The hash160 result
        """
        sha256_hash = hashlib.sha256(data).digest()
        ripemd160_hash = hashlib.new('ripemd160')
        ripemd160_hash.update(sha256_hash)
        return ripemd160_hash.digest()

    def _create_p2pkh_address(self, public_key_bytes: bytes) -> str:
        """
        Create a P2PKH (legacy) address from a public key.

        Args:
            public_key_bytes: The compressed public key bytes

        Returns:
            The Bitcoin address
        """
        # Hash the public key
        h160 = self._hash160(public_key_bytes)

        # Add version byte (0x00 for Bitcoin mainnet)
        versioned = P2PKH_VERSION_BYTE + h160

        # Base58Check encode
        return base58.b58encode_check(versioned).decode('ascii')

    def _create_p2sh_p2wpkh_address(self, public_key_bytes: bytes) -> str:
        """
        Create a P2SH-wrapped SegWit address from a public key.

        Args:
            public_key_bytes: The compressed public key bytes

        Returns:
            The Bitcoin address
        """
        # Hash the public key
        keyhash = self._hash160(public_key_bytes)

        # Create the redeem script (0x0014 + keyhash)
        redeem_script = P2WPKH_SCRIPT_PREFIX + keyhash

        # Hash the redeem script
        script_hash = self._hash160(redeem_script)

        # Add version byte (0x05 for P2SH)
        versioned = P2SH_VERSION_BYTE + script_hash

        # Base58Check encode
        return base58.b58encode_check(versioned).decode('ascii')

    def _create_p2wpkh_address(self, public_key_bytes: bytes) -> str:
        """
        Create a P2WPKH (native SegWit) address from a public key.

        Args:
            public_key_bytes: The compressed public key bytes

        Returns:
            The Bitcoin address
        """
        # Hash the public key
        keyhash = self._hash160(public_key_bytes)

        # Convert to 5-bit words for bech32 encoding
        # Witness version 0 + key hash
        witness_program = keyhash

        # Encode with bech32
        address = bech32.encode('bc', 0, witness_program)

        return address

    def generate_address(self, index: int, change: bool = False) -> str:
        """
        Generate a Bitcoin address for the given index.

        Args:
            index: The address index
            change: Whether to use the change path (1) or receive path (0)

        Returns:
            The Bitcoin address
        """
        # Determine the path
        change_index = 1 if change else 0
        path = f"{change_index}/{index}"

        # Derive the child key
        derived_key = self._derive_path(path)

        # Get the compressed public key bytes
        public_key_bytes = derived_key.to_string("compressed")

        # Create the appropriate address type
        if self.key_type == KeyType.XPUB:
            return self._create_p2pkh_address(public_key_bytes)
        elif self.key_type == KeyType.YPUB:
            return self._create_p2sh_p2wpkh_address(public_key_bytes)
        elif self.key_type == KeyType.ZPUB:
            return self._create_p2wpkh_address(public_key_bytes)
        else:
            raise ValueError(f"Unsupported key type: {self.key_type}")

    def generate_addresses(
        self,
        start_index: int = 0,
        count: int = 10,
        change: bool = False
    ) -> List[Tuple[int, str]]:
        """
        Generate multiple Bitcoin addresses.

        Args:
            start_index: The starting address index
            count: The number of addresses to generate
            change: Whether to use the change path (1) or receive path (0)

        Returns:
            A list of (index, address) tuples
        """

        addresses = []
        for i in range(start_index, start_index + count):
            address = self.generate_address(i, change)
            addresses.append((i, address))

        return addresses
