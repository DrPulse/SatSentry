"""
Tests for the address monitoring functionality.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.btc_addr_gen.core.key_types import KeyType

from app.services.address_monitor import (
    is_valid_bitcoin_address,
    add_single_address,
    add_extended_public_key,
    get_all_addresses,
    get_all_extended_keys,
    delete_address,
    delete_extended_key
)

# Sample test data
SAMPLE_ADDRESS = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
SAMPLE_XPUB = "xpub6CUGRUonZSQ4TWtTMmzXdrXDtypWKiKrhko4egpiMZbpiaQL2jkwSB1icqYh2cfDfVxdx4df189oLKnC5fSwqPfgyP3hooxujYzAu3fDVmz"


@pytest.fixture(scope="function")
def setup_test_files(monkeypatch):
    """Set up test files by mocking the file I/O functions."""
    # Create in-memory storage
    single_addresses = {}
    extended_keys = {}

    # Mock the load and save functions for single addresses
    def mock_load_single_addresses():
        return single_addresses.copy()

    def mock_save_single_addresses(addresses):
        nonlocal single_addresses
        single_addresses = addresses.copy()

    # Mock the load and save functions for extended keys
    def mock_load_extended_keys():
        return extended_keys.copy()

    def mock_save_extended_keys(keys):
        nonlocal extended_keys
        extended_keys = keys.copy()

    # Mock the ensure_data_files_exist function to do nothing
    def mock_ensure_data_files_exist():
        pass

    # Patch all the functions
    monkeypatch.setattr("app.services.extended_key_manager._ensure_data_files_exist", mock_ensure_data_files_exist)
    monkeypatch.setattr("app.services.address_monitor._ensure_data_files_exist", mock_ensure_data_files_exist)

    monkeypatch.setattr("app.services.address_monitor._load_single_addresses", mock_load_single_addresses)
    monkeypatch.setattr("app.services.address_monitor._save_single_addresses", mock_save_single_addresses)

    monkeypatch.setattr("app.services.extended_key_manager._load_extended_keys", mock_load_extended_keys)
    monkeypatch.setattr("app.services.extended_key_manager._save_extended_keys", mock_save_extended_keys)
    monkeypatch.setattr("app.services.address_monitor._load_extended_keys", mock_load_extended_keys)
    monkeypatch.setattr("app.services.address_monitor._save_extended_keys", mock_save_extended_keys)

    # No need to patch module-level functions as they don't exist in this module

    # No need to yield anything as we're using in-memory storage
    yield


def test_is_valid_bitcoin_address():
    """Test Bitcoin address validation."""
    # Valid addresses
    assert is_valid_bitcoin_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")  # Legacy
    assert is_valid_bitcoin_address("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy")  # P2SH
    assert is_valid_bitcoin_address("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")  # Bech32

    # Invalid addresses
    assert not is_valid_bitcoin_address("invalid")
    assert not is_valid_bitcoin_address("1234567890")
    assert not is_valid_bitcoin_address("")


def test_add_single_address(setup_test_files):
    """Test adding a single address."""
    # Add an address
    add_single_address(SAMPLE_ADDRESS, "Test Address")

    # Check if the address was added
    addresses = get_all_addresses()
    assert SAMPLE_ADDRESS in addresses
    assert addresses[SAMPLE_ADDRESS]["label"] == "Test Address"

    # Try to add the same address again
    with pytest.raises(ValueError):
        add_single_address(SAMPLE_ADDRESS, "Duplicate")


def test_delete_address(setup_test_files):
    """Test deleting an address."""
    # Add an address
    add_single_address(SAMPLE_ADDRESS, "Test Address")

    # Delete the address
    delete_address(SAMPLE_ADDRESS)

    # Check if the address was deleted
    addresses = get_all_addresses()
    assert SAMPLE_ADDRESS not in addresses

    # Try to delete a non-existent address
    with pytest.raises(ValueError):
        delete_address("nonexistent")


@patch("app.services.extended_key_manager.AddressGenerator")
def test_add_extended_public_key(mock_generator, setup_test_files):
    """Test adding an extended public key."""
    # Mock the AddressGenerator
    mock_instance = MagicMock()
    mock_instance.key_type.name = "XPUB"
    mock_instance.generate_addresses.return_value = [(0, "address1"), (1, "address2")]
    mock_generator.return_value = mock_instance

    # Add an extended key
    with patch("app.services.extended_key_manager.is_valid_extended_key", return_value=True), \
         patch("app.services.extended_key_manager.detect_key_type", return_value=KeyType.XPUB):
        add_extended_public_key(extended_key=SAMPLE_XPUB,gap_limit=20, initial_addresses= 10,label= "Test Key")

    # Check if the key was added
    keys = get_all_extended_keys()
    assert SAMPLE_XPUB in keys
    assert keys[SAMPLE_XPUB]["label"] == "Test Key"
    # Check that there are derivation paths
    assert "derivation_paths" in keys[SAMPLE_XPUB]
    # Get the first derivation path
    deriv_path = list(keys[SAMPLE_XPUB]["derivation_paths"].keys())[0]
    # Check that there are derived addresses
    assert len(keys[SAMPLE_XPUB]["derivation_paths"][deriv_path]["derived_addresses"]) >= 2


@patch("app.services.extended_key_manager.AddressGenerator")
def test_delete_extended_key(mock_generator, setup_test_files):
    """Test deleting an extended key."""
    # Mock the AddressGenerator
    mock_instance = MagicMock()
    mock_instance.key_type.name = "XPUB"
    mock_instance.generate_addresses.return_value = [(0, "address1"), (1, "address2")]
    mock_generator.return_value = mock_instance

    # Add an extended key
    with patch("app.services.extended_key_manager.is_valid_extended_key", return_value=True), \
         patch("app.services.extended_key_manager.detect_key_type", return_value=KeyType.XPUB):
        add_extended_public_key(SAMPLE_XPUB, "Test Key")

    # Delete the key
    delete_extended_key(SAMPLE_XPUB)

    # Check if the key was deleted
    keys = get_all_extended_keys()
    assert SAMPLE_XPUB not in keys

    # Try to delete a non-existent key
    with pytest.raises(ValueError):
        delete_extended_key("nonexistent")
