#!/usr/bin/env python3
"""
SatSentry - Main Application Entry Point

This script initializes and runs the SatSentry application.
It sets up the web server and starts the address monitoring scheduler.
"""

import os
import logging
from app import create_app
from waitress import serve

# TODO: add log file and log rotation
# TODO: cleanup html templates ?
# TODO: check coverage and refactor tests to be more useful and easier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        #logging.FileHandler('/app/logs/bitcoin_address_monitor.log')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main application entry point."""
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)

    # Initialize default settings if they don't exist
    if not os.path.exists('data/settings.json'):
        from app.services.settings import initialize_settings
        initialize_settings()

    app = create_app()

    # Start the scheduler - the singleton pattern ensures it only runs once
    from app.services.scheduler import start_scheduler
    start_scheduler()

    # Run the app
    serve(app, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    try:
        logger.info("Starting SatSentry...")
        main()
    except Exception as e:
        logger.exception(f"Error starting application: {e}")
