"""
Settings management for the SatSentry application.
"""

import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# File paths
DATA_DIR = 'data'
SETTINGS_FILE = f'{DATA_DIR}/settings.json'
SINGLE_ADDRESSES_FILE = f'{DATA_DIR}/single_addresses.json'
EXTENDED_KEYS_FILE = f'{DATA_DIR}/extended_public_keys.json'

DEFAULT_SETTINGS = {
    'check_interval': 300,  # 5 minutes
    'use_self_hosted': False,
    'node_url': 'https://mempool.space',
    'node_port': 443,
    'discord_webhook': '',
    'gap': 20,
    'initial_addresses': 10,
    'check_interval_min_self_hosted': 30,
}

def initialize_settings() -> None:
    """Initialize settings file with default values if it doesn't exist."""
    if not os.path.exists(SETTINGS_FILE):
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)
        logger.info("Initialized default settings")

def get_settings() -> Dict[str, Any]:
    """Get current settings."""
    if not os.path.exists(SETTINGS_FILE):
        initialize_settings()

    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
        return settings
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return DEFAULT_SETTINGS.copy()

def update_settings(new_settings: Dict[str, Any]) -> None:
    """Update settings with new values."""

    # Merge with existing settings
    settings = get_settings()
    settings.update(new_settings)

    if not validate_settings():
        raise ValueError("Invalid settings configuration")

    # Save updated settings
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        logger.info("Settings updated successfully")
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise ValueError(f"Failed to save settings: {e}")

def validate_settings() -> bool:
    """Validate current settings."""
    settings = get_settings()

    # Check required fields
    required_fields = ['check_interval', 'node_url', 'node_port', 'gap', 'initial_addresses']
    for field in required_fields:
        if field not in settings:
            logger.error(f"Missing required setting: {field}")
            return False

    # Check check_interval
    min_interval = DEFAULT_SETTINGS['check_interval_min_self_hosted'] if settings.get('use_self_hosted', False) else DEFAULT_SETTINGS['check_interval']
    if settings['check_interval'] < min_interval:
        logger.error(f"Check interval must be at least {min_interval} seconds")
        return False

    return True


def get_file_path(path_key: str) -> str:
    """Get a file path from settings.

    Args:
        path_key: The key for the file path in settings

    Returns:
        The file path
    """
    # Define standard paths
    paths = {
        'data_dir': DATA_DIR,
        'settings_file': SETTINGS_FILE,
        'single_addresses_file': SINGLE_ADDRESSES_FILE,
        'extended_keys_file': EXTENDED_KEYS_FILE,
    }

    # Return the path if it exists in our mapping
    if path_key in paths:
        return paths[path_key]

    # Default to a file in the data directory if not found
    return f"{DATA_DIR}/{path_key}.json"
