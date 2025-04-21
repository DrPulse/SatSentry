"""
Tests for the notification service.
"""

from unittest.mock import patch, MagicMock

from app.services.notification import (
    _format_btc_amount,
    _format_fee_rate,
    send_transaction_notification
)


def test_format_btc_amount():
    """Test BTC amount formatting."""
    assert _format_btc_amount(100000000) == "1.00000000 BTC"
    assert _format_btc_amount(50000000) == "0.50000000 BTC"
    assert _format_btc_amount(123456) == "0.00123456 BTC"
    assert _format_btc_amount(0) == "0.00000000 BTC"


def test_format_fee_rate():
    """Test fee rate formatting."""
    assert _format_fee_rate(10.5) == "10.50 sat/vB"
    assert _format_fee_rate(1) == "1.00 sat/vB"
    assert _format_fee_rate(0) == "0.00 sat/vB"


# TODO: Add more tests for the notification service like testing the actual sending of notifications
