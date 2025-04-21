"""
Scheduler service for SatSentry.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.services.settings import get_settings, DEFAULT_SETTINGS
from app.services.address_monitor import check_all_addresses
from app.services.notification import send_multiple_transaction_notifications

logger = logging.getLogger(__name__)

class AddressScheduler:
    """Singleton scheduler for address monitoring."""

    _instance: Optional['AddressScheduler'] = None

    @classmethod
    def get_instance(cls) -> 'AddressScheduler':
        """Get or create the scheduler instance."""
        if cls._instance is None:
            cls._instance = AddressScheduler()
        return cls._instance

    def __init__(self):
        """Initialize the scheduler."""
        if AddressScheduler._instance is not None:
            raise RuntimeError("Scheduler is a singleton. Use get_instance() instead.")

        self._thread = None
        self._running = False
        self._paused = False  # Flag to indicate if scheduler is paused
        self._checking = False  # Flag to indicate when actively checking addresses
        self._last_check_time = None
        self._next_check_time = None
        self._paused_seconds_remaining = None  # Store remaining seconds when paused
        self._pause_time = None  # Store the time when paused
        self._initialized = False

    def start(self) -> bool:
        """Start the address check scheduler."""
        if self._thread and self._thread.is_alive():
            logger.warning("Scheduler already running")
            return False

        self._running = True
        self._initialized = True

        # Set initial next check time
        settings = get_settings()
        check_interval = settings.get('check_interval', DEFAULT_SETTINGS['check_interval'])
        self._last_check_time = datetime.now()
        self._next_check_time = self._last_check_time + timedelta(seconds=check_interval)

        self._thread = threading.Thread(target=self._check_addresses_task)
        self._thread.daemon = True
        self._thread.start()

        logger.info("Scheduler started")
        return True

    def pause(self) -> bool:
        """Pause the address check scheduler."""
        if not self._running or not self._thread or not self._thread.is_alive():
            logger.warning("Scheduler not running")
            return False

        if self._paused:
            logger.warning("Scheduler already paused")
            return False

        logger.info("Pausing scheduler")
        self._paused = True
        self._pause_time = datetime.now()

        # Store the remaining time when paused
        if self._next_check_time:
            if self._next_check_time > self._pause_time:
                self._paused_seconds_remaining = (self._next_check_time - self._pause_time).total_seconds()
            else:
                self._paused_seconds_remaining = 0
        else:
            self._paused_seconds_remaining = 0

        logger.info(f"Scheduler paused with {self._paused_seconds_remaining:.1f} seconds remaining until next check")
        return True

    def resume(self) -> bool:
        """Resume the address check scheduler."""
        if not self._running or not self._thread or not self._thread.is_alive():
            logger.warning("Scheduler not running")
            return False

        if not self._paused:
            logger.warning("Scheduler not paused")
            return False

        logger.info("Resuming scheduler")

        # Update the next check time based on the stored remaining time
        if self._paused_seconds_remaining is not None:
            # Calculate how much time has passed since pausing
            resume_time = datetime.now()

            # Set the next check time to now + remaining seconds
            self._next_check_time = resume_time + timedelta(seconds=self._paused_seconds_remaining)
            logger.info(f"Next check rescheduled for {self._next_check_time} ({self._paused_seconds_remaining:.1f} seconds from now)")

            # Reset the paused seconds
            self._paused_seconds_remaining = None
            self._pause_time = None

        self._paused = False
        logger.info("Scheduler resumed")
        return True

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the scheduler.

        Returns:
            Dictionary with scheduler status information
        """
        settings = get_settings()
        check_interval = settings.get('check_interval', DEFAULT_SETTINGS['check_interval'])

        # Default status if scheduler is not initialized
        if not self._initialized:
            return {
                'running': False,
                'paused': False,
                'checking': False,
                'last_check': None,
                'next_check': None,
                'check_interval': check_interval,
                'seconds_to_next_check': 0
            }

        status = {
            'running': self._running,
            'paused': self._paused,
            'checking': self._checking,
            'last_check': self._last_check_time.strftime('%Y-%m-%d %H:%M:%S') if self._last_check_time else None,
            'next_check': self._next_check_time.strftime('%Y-%m-%d %H:%M:%S') if self._next_check_time else None,
            'check_interval': check_interval
        }

        # Calculate time until next check
        if self._paused and self._paused_seconds_remaining is not None:
            # When paused, use the stored remaining time
            status['seconds_to_next_check'] = int(self._paused_seconds_remaining)
        elif self._next_check_time:
            now = datetime.now()
            if self._next_check_time > now:
                seconds_remaining = (self._next_check_time - now).total_seconds()
                status['seconds_to_next_check'] = int(seconds_remaining)
            else:
                # If we're currently checking addresses, return 0 for countdown
                # Otherwise, we're overdue for a check (could happen if the thread was paused)
                status['seconds_to_next_check'] = 0
        else:
            status['seconds_to_next_check'] = 0

        return status

    def _check_addresses_task(self):
        """Background task to check addresses."""
        logger.info("Starting address check task")

        # Initialize next check time
        settings = get_settings()
        check_interval = settings.get('check_interval', DEFAULT_SETTINGS['check_interval'])
        self._next_check_time = datetime.now() + timedelta(seconds=check_interval)

        while self._running:
            try:
                # Skip checks if paused
                if self._paused:
                    # When paused, just sleep a bit and continue
                    time.sleep(5)
                    continue

                # Wait until it's time for the next check
                now = datetime.now()
                if self._next_check_time > now:
                    # Not time yet, sleep a bit
                    sleep_time = min((self._next_check_time - now).total_seconds(), 5)
                    time.sleep(sleep_time)
                    continue

                # Get current settings (might have changed)
                settings = get_settings()
                check_interval = settings.get('check_interval', DEFAULT_SETTINGS['check_interval'])

                # Set checking flag to true
                self._checking = True

                # Record the check start time
                self._last_check_time = datetime.now()
                logger.info(f"Checking addresses at {self._last_check_time}")

                # Perform the check
                new_transactions = check_all_addresses()

                if new_transactions:
                    logger.info(f"Found {len(new_transactions)} new transactions")
                    # Send notifications
                    if send_multiple_transaction_notifications(new_transactions):
                        logger.info(f"Successfully sent batch notification for {len(new_transactions)} transactions")
                    else:
                        logger.error("Failed to send batch notification")
                else:
                    logger.info("No new transactions found")

                # Calculate next check time based on when the current check completes
                # This ensures the full interval between the end of one check and the start of the next
                now = datetime.now()
                self._next_check_time = now + timedelta(seconds=check_interval)

                logger.info(f"Next check scheduled for {self._next_check_time}")

                # Set checking flag to false
                self._checking = False

            except Exception as e:
                logger.exception(f"Error in address check task: {e}")
                # Reset checking flag in case of error
                self._checking = False
                # Sleep for a bit before retrying
                time.sleep(60)
                # Reschedule next check
                self._next_check_time = datetime.now() + timedelta(seconds=check_interval)

# Compatibility functions for existing code
def start_scheduler() -> bool:
    """Start the address check scheduler."""
    return AddressScheduler.get_instance().start()

def pause_scheduler() -> bool:
    """Pause the address check scheduler."""
    return AddressScheduler.get_instance().pause()

def resume_scheduler() -> bool:
    """Resume the address check scheduler."""
    return AddressScheduler.get_instance().resume()

def get_scheduler_status() -> Dict[str, Any]:
    """Get the current status of the scheduler."""
    return AddressScheduler.get_instance().get_status()
