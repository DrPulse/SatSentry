"""
Notification service for SatSentry.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from discord_webhook import DiscordWebhook, DiscordEmbed

from app.services.settings import get_settings
from app.services import mempool_api
from app.services.address_monitor import _determine_tx_direction

logger = logging.getLogger(__name__)

def _format_btc_amount(satoshis: int) -> str:
    """
    Format a satoshi amount as BTC.

    Args:
        satoshis: Amount in satoshis

    Returns:
        Formatted BTC amount
    """
    btc = satoshis / 100000000
    return f"{btc:.8f} BTC"

def _format_fee_rate(fee_rate: float) -> str:
    """
    Format a fee rate.

    Args:
        fee_rate: Fee rate in sat/vB

    Returns:
        Formatted fee rate
    """
    return f"{fee_rate:.2f} sat/vB"

def _estimate_confirmation_time(fee_rate: float) -> str:
    """
    Estimate confirmation time based on fee rate.

    Args:
        fee_rate: Fee rate in sat/vB

    Returns:
        Estimated confirmation time
    """
    try:
        fee_estimates = mempool_api.get_fee_estimates()

        if fee_rate >= fee_estimates.get('fastestFee', 0):
            return "~10-20 minutes (next block)"
        elif fee_rate >= fee_estimates.get('halfHourFee', 0):
            return "~30 minutes"
        elif fee_rate >= fee_estimates.get('hourFee', 0):
            return "~1 hour"
        else:
            return "More than 1 hour"
    except Exception as e:
        logger.error(f"Error estimating confirmation time: {e}")
        return "Unknown"

def _get_mempool_time(txid: str) -> str:
    """
    Get time spent in mempool for a transaction.

    Args:
        txid: Transaction ID

    Returns:
        Time spent in mempool or confirmation time
    """
    try:
        tx_details = mempool_api.get_transaction_details(txid)

        # Check if the transaction is confirmed
        if 'status' in tx_details and tx_details['status'].get('confirmed', False) and 'block_time' in tx_details['status']:
            # Transaction is confirmed, show confirmation time
            block_time = datetime.fromtimestamp(tx_details['status']['block_time'])
            return f"Confirmed on {block_time.strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            # Transaction is still in mempool
            # We don't have a reliable way to know when it entered the mempool,
            # so we'll just say it's unconfirmed
            return "Unconfirmed"
    except Exception as e:
        logger.error(f"Error getting mempool time: {e}")
        return "Unknown"

def send_transaction_notification(tx_data: Dict[str, Any]) -> bool:
    """
    Send a transaction notification via Discord webhook.

    Args:
        tx_data: Transaction data containing:
            - address: The monitored Bitcoin address
            - label: Optional label for the address
            - latest_tx: Transaction details including txid

    Returns:
        True if the notification was sent successfully, False otherwise
    """
    settings = get_settings()
    webhook_url = settings.get('discord_webhook')

    if not webhook_url:
        logger.warning("Discord webhook URL not configured")
        return False

    try:
        webhook = DiscordWebhook(url=webhook_url)


        # Get transaction details
        txid = tx_data.get('latest_tx', {}).get('txid')
        if not txid:
            logger.error("Transaction ID not found in data")
            return False

        address = tx_data.get('address')
        if not address:
            logger.error("Address not found in tx_data")
            return False

        tx_details = mempool_api.get_transaction_details(txid)

        # Determine transaction direction using the existing function
        direction = _determine_tx_direction(address, tx_details)

        # Calculate amount based on direction
        amount = 0
        if direction == 'incoming':
            for vout in tx_details.get('vout', []):
                if vout.get('scriptpubkey_address') == address:
                    amount += vout.get('value', 0)
        else:  # outgoing
            inputs_from_us = sum(
                vin.get('prevout', {}).get('value', 0)
                for vin in tx_details.get('vin', [])
                if vin.get('prevout', {}).get('scriptpubkey_address') == address
            )
            outputs_to_us = sum(
                vout.get('value', 0)
                for vout in tx_details.get('vout', [])
                if vout.get('scriptpubkey_address') == address
            )
            amount = inputs_from_us - outputs_to_us

        # Calculate fee
        fee = tx_details.get('fee', 0)

        # Calculate fee rate
        fee_rate = tx_details.get('fee_rate', 0)

        # Create embed
        color = 0x00ff00 if direction == 'incoming' else 0xff0000  # Green for incoming, red for outgoing
        title = f"{'Incoming' if direction == 'incoming' else 'Outgoing'} Transaction Detected"

        embed = DiscordEmbed(
            title=title,
            color=color
        )

        # Add fields
        embed.add_embed_field(
            name="Address",
            value=f"`{tx_data.get('address')}`\n{tx_data.get('label', '')}"
        )

        embed.add_embed_field(
            name="Amount",
            value=_format_btc_amount(amount)
        )

        # Get mempool URL based on settings
        mempool_url = mempool_api.get_api_url().split("/api")[0]

        embed.add_embed_field(
            name="Transaction ID",
            value=f"[{txid[:8]}...{txid[-8:]}]({mempool_url}/tx/{txid})"
        )

        if direction == 'outgoing':
            # Find the main recipient (largest output not going back to our address)
            largest_output = 0
            recipient = None

            for vout in tx_details.get('vout', []):
                if vout.get('scriptpubkey_address') != tx_data.get('address') and vout.get('value', 0) > largest_output:
                    largest_output = vout.get('value', 0)
                    recipient = vout.get('scriptpubkey_address')

            if recipient:
                embed.add_embed_field(
                    name="Recipient",
                    value=f"`{recipient}`"
                )

        embed.add_embed_field(
            name="Fee",
            value=_format_btc_amount(fee)
        )

        embed.add_embed_field(
            name="Fee Rate",
            value=_format_fee_rate(fee_rate)
        )

        embed.add_embed_field(
            name="Estimated Confirmation",
            value=_estimate_confirmation_time(fee_rate)
        )

        embed.add_embed_field(
            name="Time in Mempool",
            value=_get_mempool_time(txid)
        )

        # Set timestamp
        embed.set_timestamp()

        # Add embed to webhook
        webhook.add_embed(embed)

        # Send webhook
        response = webhook.execute()

        if response.status_code == 200:
            logger.info(f"Notification sent for transaction {txid}")
            return True
        else:
            logger.error(f"Failed to send notification: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False

def send_multiple_transaction_notifications(tx_data_list: List[Dict[str, Any]]) -> int:
    """
    Send notifications for multiple transactions.

    Args:
        tx_data_list: List of transaction data

    Returns:
        Number of notifications sent successfully
    """
    success_count = 0

    for tx_data in tx_data_list:
        if send_transaction_notification(tx_data):
            success_count += 1

    return success_count
