"""
Tests for the extended key manager functionality with isolated mocks.
"""

from unittest.mock import patch, MagicMock

from app.services import extended_key_manager
from app.btc_addr_gen.core.key_types import KeyType

# Sample test data
SAMPLE_XPUB = "xpub6CUGRUonZSQ4TWtTMmzXdrXDtypWKiKrhko4egpiMZbpiaQL2jkwSB1icqYh2cfDfVxdx4df189oLKnC5fSwqPfgyP3hooxujYzAu3fDVmz"
SAMPLE_XPUB2 = "xpub6BosfCnifzxcFwrSzQiqu2DBVTshkCXacvNsWGYJVVhhawA7d4R5WSWGFNbi8Aw6ZRc1brxMyWMzG3DSSSSoekkudhUd9yLb6qx39T9nMdj"
SAMPLE_XPUB3 = "xpub6CnQkivUEH9bSbWVWfDLCtigKKgnSWGaVSRyCbN2QNBJzuvHT1vUQpgSpYYB4tLQVY9NN7kNyNxiUZZEAo2SFxpfGfJ1aFNWxjLz3Ykj6Yv"
SAMPLE_XPUB4 = "xpub6D4BDPcP2GT577Vvch3R8wDkScZWzQzMMUm3PWbmWvVJrZwQY4VUNgqFJPMM3No2dFDFGTsxxpG5uJh7n7epu4trkrX7x7DogT5Uv6fcLW5"
SAMPLE_XPUB5 = "xpub6FHa3pjLCk84BayeJxFW2SP4XRrFd1JYnxeLeU8EqN3vDfZmbqBqaGJAyiLjTAwm6ZLRQUMv1ZACTj37sR62cfN7fe5JnJ7dh8zL4fiyLHV"
SAMPLE_XPUB6 = "xpub6FnCn6nSzZAw5Tw7cgR9bi15UV96gLZhjDstkXXxvCLsUXBGXPdSnLFbdpq8p9HmGsApME5hQTZ3emM2rnY5agb9rXpVGyy3bdW6EEgAtqt"
SAMPLE_XPUB7 = "xpub6H1LXWLaKsWFhvm6RVpEL9P4KfRZSW7abD2ttkWP3SSQvnyA8FSVqNTEcYFgJS2UaFcxupHiYkro49S8yGasTvXEYBVPamhGW6cFJodrTHy"

@patch("app.services.extended_key_manager.AddressGenerator")
@patch("app.services.extended_key_manager._load_extended_keys")
@patch("app.services.extended_key_manager._save_extended_keys")
def test_add_extended_key(mock_save, mock_load, mock_generator):
    """Test adding an extended key with the manager."""
    # Mock the load function to return an empty dict
    mock_load.return_value = {}

    # Mock the AddressGenerator
    mock_instance = MagicMock()
    mock_instance.key_type.name = "XPUB"
    mock_instance.generate_addresses.return_value = [(0, "address1"), (1, "address2"), (2, "address3")]
    mock_generator.return_value = mock_instance

    # Add an extended key
    with patch("app.services.extended_key_manager.is_valid_extended_key", return_value=True), \
        patch("app.services.extended_key_manager.detect_key_type", return_value=KeyType.XPUB):
        extended_key_manager.add_extended_key(
            extended_key=SAMPLE_XPUB,
            label="Test Key",
            derivation_path="m/44'/0'/0'",
            start_index=0,
            initial_addresses=3,
            gap_limit=20
        )

    # Check that save was called with the correct data
    assert mock_save.called
    saved_data = mock_save.call_args[0][0]
    assert SAMPLE_XPUB in saved_data
    assert saved_data[SAMPLE_XPUB]["key_type"] == "XPUB"
    assert saved_data[SAMPLE_XPUB]["label"] == "Test Key"

    # Check derivation path data
    path_data = saved_data[SAMPLE_XPUB]["derivation_paths"]["m/44'/0'/0'"]
    assert path_data["start_index"] == 0
    assert path_data["current_index"] == 2  # 3 addresses (0, 1, 2)
    assert path_data["gap_limit"] == 20

    # Check derived addresses
    derived_addresses = path_data["derived_addresses"]
    assert len(derived_addresses) == 3
    assert "m/44'/0'/0'/0/0" in derived_addresses
    assert derived_addresses["m/44'/0'/0'/0/0"]["address"] == "address1"
    assert not derived_addresses["m/44'/0'/0'/0/0"]["used"]


@patch("app.services.extended_key_manager.AddressGenerator")
@patch("app.services.extended_key_manager._load_extended_keys")
@patch("app.services.extended_key_manager._save_extended_keys")
def test_ensure_gap_limit_no_used_addresses(mock_save, mock_load, mock_generator):
    """Test ensuring gap limit when no addresses are used."""
    # Mock the load function to return a dictionary with an extended key
    mock_data = {
        SAMPLE_XPUB2: {
            "label": "Test Key",
            "key_type": "XPUB",
            "derivation_paths": {
                "m/44'/0'/0'": {
                    "start_index": 0,
                    "current_index": 2,  # 3 addresses (0, 1, 2)
                    "gap_limit": 5,
                    "derived_addresses": {
                        "m/44'/0'/0'/0/0": {"address": "address1", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/1": {"address": "address2", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/2": {"address": "address3", "used": False, "last_tx": None}
                    }
                }
            }
        }
    }
    mock_load.return_value = mock_data

    # Mock the AddressGenerator
    mock_instance = MagicMock()
    mock_instance.key_type.name = "XPUB"
    mock_instance.generate_addresses.return_value = [(3, "address4"), (4, "address5")]
    mock_generator.return_value = mock_instance

    # Since no addresses are used and we have 3 addresses with a gap limit of 5,
    # ensure_gap_limit should generate 2 more addresses
    with patch("app.services.mempool_api.get_address_transactions", return_value=[]):
        extended_key_manager.ensure_gap_limit(SAMPLE_XPUB2, "m/44'/0'/0'")

    # Check that save was called with the correct data
    assert mock_save.called
    saved_data = mock_save.call_args[0][0]

    # Check the updated data
    path_data = saved_data[SAMPLE_XPUB2]["derivation_paths"]["m/44'/0'/0'"]
    derived_addresses = path_data["derived_addresses"]

    # Check that we now have 5 addresses
    assert len(derived_addresses) == 5
    assert "m/44'/0'/0'/0/3" in derived_addresses
    assert "m/44'/0'/0'/0/4" in derived_addresses
    assert derived_addresses["m/44'/0'/0'/0/3"]["address"] == "address4"
    assert derived_addresses["m/44'/0'/0'/0/4"]["address"] == "address5"


@patch("app.services.extended_key_manager.AddressGenerator")
@patch("app.services.extended_key_manager._load_extended_keys")
@patch("app.services.extended_key_manager._save_extended_keys")
def test_ensure_gap_limit_with_used_addresses(mock_save, mock_load, mock_generator):
    """Test ensuring gap limit when some addresses are used."""
    # Mock the load function to return a dictionary with an extended key
    mock_data = {
        SAMPLE_XPUB3: {
            "label": "Test Key",
            "key_type": "XPUB",
            "derivation_paths": {
                "m/44'/0'/0'": {
                    "start_index": 0,
                    "current_index": 5,  # 6 addresses (0, 1, 2, 3, 4, 5)
                    "gap_limit": 5,
                    "derived_addresses": {
                        "m/44'/0'/0'/0/0": {"address": "address1", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/1": {"address": "address2", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/2": {"address": "address3", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/3": {"address": "address4", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/4": {"address": "address5", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/5": {"address": "address6", "used": False, "last_tx": None}
                    }
                }
            }
        }
    }
    mock_load.return_value = mock_data

    # Mark the first two addresses as used
    mock_data[SAMPLE_XPUB3]["derivation_paths"]["m/44'/0'/0'"]["derived_addresses"]["m/44'/0'/0'/0/0"]["used"] = True
    mock_data[SAMPLE_XPUB3]["derivation_paths"]["m/44'/0'/0'"]["derived_addresses"]["m/44'/0'/0'/0/1"]["used"] = True

    # Mock the AddressGenerator
    mock_instance = MagicMock()
    mock_instance.key_type.name = "XPUB"
    mock_instance.generate_addresses.return_value = [(6, "address7")]
    mock_generator.return_value = mock_instance

    # Since addresses 0 and 1 are used, and we have addresses 2, 3, 4, 5 unused,
    # we already have 4 consecutive unused addresses. With a gap limit of 5,
    # ensure_gap_limit should generate 1 more address
    with patch("app.services.mempool_api.get_address_transactions", return_value=[]):
        extended_key_manager.ensure_gap_limit(SAMPLE_XPUB3, "m/44'/0'/0'")

    # Check that save was called with the correct data
    assert mock_save.called
    saved_data = mock_save.call_args[0][0]

    # Check the updated data
    path_data = saved_data[SAMPLE_XPUB3]["derivation_paths"]["m/44'/0'/0'"]
    derived_addresses = path_data["derived_addresses"]

    # Check that we now have 7 addresses
    assert len(derived_addresses) == 7
    assert "m/44'/0'/0'/0/6" in derived_addresses
    assert derived_addresses["m/44'/0'/0'/0/6"]["address"] == "address7"


@patch("app.services.extended_key_manager.AddressGenerator")
@patch("app.services.extended_key_manager._load_extended_keys")
@patch("app.services.extended_key_manager._save_extended_keys")
def test_ensure_gap_limit_with_transactions_in_last_addresses(mock_save, mock_load, mock_generator):
    """Test ensuring gap limit when transactions are found in the last addresses."""
    # Mock the load function to return a dictionary with an extended key
    mock_data = {
        SAMPLE_XPUB4: {
            "label": "Test Key",
            "key_type": "XPUB",
            "derivation_paths": {
                "m/44'/0'/0'": {
                    "start_index": 0,
                    "current_index": 4,  # 5 addresses (0, 1, 2, 3, 4)
                    "gap_limit": 5,
                    "derived_addresses": {
                        "m/44'/0'/0'/0/0": {"address": "address1", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/1": {"address": "address2", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/2": {"address": "address3", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/3": {"address": "address4", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/4": {"address": "address5", "used": False, "last_tx": None}
                    }
                }
            }
        }
    }
    mock_load.return_value = mock_data

    # Mark the last address as used (simulating a transaction in the last address)
    mock_data[SAMPLE_XPUB4]["derivation_paths"]["m/44'/0'/0'"]["derived_addresses"]["m/44'/0'/0'/0/4"]["used"] = True

    # Mock the AddressGenerator
    mock_instance = MagicMock()
    mock_instance.key_type.name = "XPUB"
    mock_instance.generate_addresses.return_value = [(5, "address6"), (6, "address7"), (7, "address8"),
                                                    (8, "address9"), (9, "address10")]
    mock_generator.return_value = mock_instance

    # Since the last address is used, we have 0 consecutive unused addresses.
    # With a gap limit of 5, ensure_gap_limit should generate 5 more addresses
    with patch("app.services.mempool_api.get_address_transactions", return_value=[]):
        extended_key_manager.ensure_gap_limit(SAMPLE_XPUB4, "m/44'/0'/0'")

    # Check that save was called with the correct data
    assert mock_save.called
    saved_data = mock_save.call_args[0][0]

    # Check the updated data
    path_data = saved_data[SAMPLE_XPUB4]["derivation_paths"]["m/44'/0'/0'"]
    derived_addresses = path_data["derived_addresses"]

    # Check that we now have 10 addresses
    assert len(derived_addresses) == 10
    assert "m/44'/0'/0'/0/9" in derived_addresses
    assert derived_addresses["m/44'/0'/0'/0/9"]["address"] == "address10"


@patch("app.services.extended_key_manager.AddressGenerator")
@patch("app.services.extended_key_manager._load_extended_keys")
@patch("app.services.extended_key_manager._save_extended_keys")
def test_update_address_used_status(mock_save, mock_load, mock_generator):
    """Test updating the used status of an address."""
    # Mock the load function to return a dictionary with an extended key
    mock_data = {
        SAMPLE_XPUB5: {
            "label": "Test Key",
            "key_type": "XPUB",
            "derivation_paths": {
                "m/44'/0'/0'": {
                    "start_index": 0,
                    "current_index": 2,  # 3 addresses (0, 1, 2)
                    "gap_limit": 5,
                    "derived_addresses": {
                        "m/44'/0'/0'/0/0": {"address": "address1", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/1": {"address": "address2", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/2": {"address": "address3", "used": False, "last_tx": None}
                    }
                }
            }
        }
    }
    mock_load.return_value = mock_data

    # Update the used status of an address
    tx_info = {
        'txid': '1234567890abcdef',
        'direction': 'incoming',
        'timestamp': '2023-01-01T12:00:00'
    }
    updated = extended_key_manager.update_address_used_status("address2", True, tx_info)

    # Check that the address was updated
    assert updated

    # Check that save was called with the correct data
    assert mock_save.called
    saved_data = mock_save.call_args[0][0]

    # Check the updated data
    path_data = saved_data[SAMPLE_XPUB5]["derivation_paths"]["m/44'/0'/0'"]
    address_data = path_data["derived_addresses"]["m/44'/0'/0'/0/1"]  # address2 is at index 1
    assert address_data["used"]
    assert address_data["last_tx"] == tx_info


@patch("app.services.extended_key_manager.AddressGenerator")
@patch("app.services.extended_key_manager._load_extended_keys")
@patch("app.services.extended_key_manager._save_extended_keys")
def test_update_gap_limit(mock_save, mock_load, mock_generator):
    """Test expanding the gap limit."""
    # Mock the load function to return a dictionary with an extended key
    mock_data = {
        SAMPLE_XPUB6: {
            "label": "Test Key",
            "key_type": "XPUB",
            "derivation_paths": {
                "m/44'/0'/0'": {
                    "start_index": 0,
                    "current_index": 2,  # 3 addresses (0, 1, 2)
                    "gap_limit": 5,
                    "derived_addresses": {
                        "m/44'/0'/0'/0/0": {"address": "address1", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/1": {"address": "address2", "used": False, "last_tx": None},
                        "m/44'/0'/0'/0/2": {"address": "address3", "used": False, "last_tx": None}
                    }
                }
            }
        }
    }
    mock_load.return_value = mock_data

    # Mock the AddressGenerator
    mock_instance = MagicMock()
    mock_instance.key_type.name = "XPUB"
    mock_instance.generate_addresses.return_value = [(3, "address4"), (4, "address5")]
    mock_generator.return_value = mock_instance

    # Expand the gap limit by 2 more addresses
    extended_key_manager.update_gap_limit(SAMPLE_XPUB6, "m/44'/0'/0'", 2)

    # Check that save was called with the correct data
    assert mock_save.called
    saved_data = mock_save.call_args[0][0]

    # Check the updated data
    path_data = saved_data[SAMPLE_XPUB6]["derivation_paths"]["m/44'/0'/0'"]
    derived_addresses = path_data["derived_addresses"]

    # Check that we still have 3 addresses, none other should be generated yet
    assert len(derived_addresses) == 3
