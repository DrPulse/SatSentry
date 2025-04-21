"""
Tests for extended public key derivation.
"""

from unittest.mock import patch
import base58

from app.btc_addr_gen.core.address_generator import AddressGenerator
from app.btc_addr_gen.core.key_types import KeyType, detect_key_type
from app.btc_addr_gen.utils.validation import is_valid_extended_key

# Sample extended keys for testing
SAMPLE_XPUB = "xpub6CUGRUonZSQ4TWtTMmzXdrXDtypWKiKrhko4egpiMZbpiaQL2jkwSB1icqYh2cfDfVxdx4df189oLKnC5fSwqPfgyP3hooxujYzAu3fDVmz"
SAMPLE_YPUB = "ypub6Ww3ibxVfGzLrAH1PNcjyAWenMTbbAosGNB6VvmSEgytSER9azLDWCxoJwW7Ke7icmizBMXrzBx9979FfaHxHcrArf3zbeJJJUZPf663zsP"
SAMPLE_ZPUB = "zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1ADqtfSdVCToUG868RvUUkgDKf31mGDtKsAYz2oz2AGutZYs"


def test_detect_key_type():
    """Test key type detection."""
    assert detect_key_type(SAMPLE_XPUB) == KeyType.XPUB
    assert detect_key_type(SAMPLE_YPUB) == KeyType.YPUB
    assert detect_key_type(SAMPLE_ZPUB) == KeyType.ZPUB
    assert detect_key_type("invalid") is None


def test_is_valid_extended_key():
    """Test extended key validation."""
    assert is_valid_extended_key(SAMPLE_XPUB) is True
    assert is_valid_extended_key(SAMPLE_YPUB) is True
    assert is_valid_extended_key(SAMPLE_ZPUB) is True
    assert is_valid_extended_key("invalid") is False
    assert is_valid_extended_key("") is False


def test_extended_key_invalid_pubkey_format():
    """Test validation fails when public key format byte is invalid."""
    # Create a key with invalid public key format (using 0x04 instead of 0x02/0x03)
    raw_bytes = (
        b'\x04\x88\xB2\x1E'  # Version bytes
        + b'\x00'            # Depth
        + b'\x00\x00\x00\x00'  # Parent fingerprint
        + b'\x00\x00\x00\x00'  # Child number
        + b'\x00' * 32       # Chain code
        + b'\x04'            # Invalid format byte (0x04)
        + b'\x00' * 32       # Rest of public key
    )
    invalid_key = base58.b58encode_check(raw_bytes).decode()

    assert is_valid_extended_key(invalid_key) is False

@patch("app.btc_addr_gen.core.address_generator.AddressGenerator._parse_extended_key")
@patch("app.btc_addr_gen.core.address_generator.AddressGenerator._derive_child_key")
def test_address_generator_initialization(mock_derive, mock_parse):
    """Test AddressGenerator initialization."""
    # Mock the key parsing
    mock_parse.return_value = None

    # Create generator
    with patch("app.btc_addr_gen.core.address_generator.detect_key_type", return_value=KeyType.XPUB):
        generator = AddressGenerator(SAMPLE_XPUB)

    # Verify
    assert generator.extended_key == SAMPLE_XPUB
    assert generator.key_type == KeyType.XPUB
    mock_parse.assert_called_once()


@patch("app.btc_addr_gen.core.address_generator.AddressGenerator._parse_extended_key")
@patch("app.btc_addr_gen.core.address_generator.AddressGenerator.generate_address")
def test_generate_addresses(mock_generate_address, mock_parse):
    """Test generating multiple addresses."""
    # Mock the key parsing and address generation
    mock_parse.return_value = None
    mock_generate_address.side_effect = lambda idx, change: f"address{idx}"

    # Create generator
    with patch("app.btc_addr_gen.core.address_generator.detect_key_type", return_value=KeyType.XPUB):
        generator = AddressGenerator(SAMPLE_XPUB)

    # Generate addresses
    addresses = generator.generate_addresses(0, 3)

    # Verify
    assert len(addresses) == 3
    assert addresses[0] == (0, "address0")
    assert addresses[1] == (1, "address1")
    assert addresses[2] == (2, "address2")
    assert mock_generate_address.call_count == 3
