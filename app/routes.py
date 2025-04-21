"""
Web routes for the SatSentry application.
"""

import json
import time
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, stream_with_context

from app.services.address_monitor import (
    add_single_address,
    add_extended_public_key,
    get_all_addresses,
    get_all_extended_keys,
    delete_address,
    delete_extended_key,
    delete_extended_key_derivation_path,
    refresh_address
)
from app.services.settings import get_settings, update_settings, DEFAULT_SETTINGS
from app.services.scheduler import get_scheduler_status, pause_scheduler, resume_scheduler
from app.services import mempool_api
from app.btc_addr_gen.utils.validation import is_valid_extended_key

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Main dashboard page."""
    # Get scheduler status
    status = get_scheduler_status()

    # Get settings
    settings = get_settings()

    return render_template(
        'index.html',
        status=status,
        settings=settings
    )

@main_bp.route('/api/scheduler-status')
def scheduler_status():
    """API endpoint for getting current scheduler status."""
    status = get_scheduler_status()
    return jsonify(status)

@main_bp.route('/api/scheduler-events')
def scheduler_events():
    """Server-Sent Events endpoint for real-time scheduler updates."""
    def generate():
        # Send initial status
        status = get_scheduler_status()
        yield f"data: {json.dumps(status)}\n\n"

        last_status = status.copy()
        last_check_time = status.get('last_check')
        last_checking_state = status.get('checking', False)

        while True:
            # Get current status
            status = get_scheduler_status()
            current_check_time = status.get('last_check')
            current_checking_state = status.get('checking', False)

            # Send update if status has changed significantly
            if (current_check_time != last_check_time or
                current_checking_state != last_checking_state or
                abs(status.get('seconds_to_next_check', 0) - last_status.get('seconds_to_next_check', 0)) >= 1):

                yield f"data: {json.dumps(status)}\n\n"

                last_status = status.copy()
                last_check_time = current_check_time
                last_checking_state = current_checking_state

            # Sleep for a short time to avoid high CPU usage
            time.sleep(0.5)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'  # Disable buffering in Nginx
        }
    )

@main_bp.route('/api/trigger-check', methods=['POST'])
def trigger_check():
    """API endpoint for triggering an immediate check."""
    try:
        # Get scheduler instance
        from app.services.scheduler import AddressScheduler
        scheduler = AddressScheduler.get_instance()

        # Set checking flag to true immediately for UI feedback
        scheduler._checking = True

        # Force next check time to now to trigger immediate check
        # This will cause the scheduler to start a check on its next iteration
        scheduler._next_check_time = datetime.now() - timedelta(seconds=1)

        # Get updated status to send to clients
        status = get_scheduler_status()

        # Create a response
        response = jsonify({
            'success': True,
            'message': "Check triggered.",
            'status': status
        })

        return response
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/pause-scheduler', methods=['POST'])
def api_pause_scheduler():
    """API endpoint for pausing the scheduler."""
    try:
        result = pause_scheduler()
        status = get_scheduler_status()

        if result:
            return jsonify({
                'success': True,
                'message': "Scheduler paused.",
                'status': status
            })
        else:
            return jsonify({
                'success': False,
                'message': "Failed to pause scheduler. It might not be running or already paused.",
                'status': status
            })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/resume-scheduler', methods=['POST'])
def api_resume_scheduler():
    """API endpoint for resuming the scheduler."""
    try:
        result = resume_scheduler()
        status = get_scheduler_status()

        if result:
            return jsonify({
                'success': True,
                'message': "Scheduler resumed.",
                'status': status
            })
        else:
            return jsonify({
                'success': False,
                'message': "Failed to resume scheduler. It might not be running or not paused.",
                'status': status
            })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/addresses')
def addresses():
    """Address management page."""
    # Get all addresses
    single_addresses = get_all_addresses()
    extended_keys = get_all_extended_keys()

    mempool_url = mempool_api.get_api_url().split("/api")[0]

    return render_template(
        'addresses.html',
        single_addresses=single_addresses,
        extended_keys=extended_keys,
        mempool_url=mempool_url
    )

@main_bp.route('/add_address', methods=['GET', 'POST'])
def add_address():
    """Add address page."""
    if request.method == 'POST':
        address_type = request.form.get('address_type')

        if address_type == 'single':
            # Add single address
            address = request.form.get('address')
            label = request.form.get('label', '')

            try:
                add_single_address(address, label)
                flash(f'Address {address} added successfully!', 'success')
                return redirect(url_for('main.addresses'))
            except ValueError as e:
                flash(f'Error adding address: {str(e)}', 'danger')

        elif address_type == 'extended':
            # Add extended public key
            extended_key = request.form.get('extended_key')
            label = request.form.get('label', '')
            derivation_path = request.form.get('derivation_path', '')
            start_index = int(request.form.get('start_index', 0))
            settings = get_settings()
            initial_addresses = int(request.form.get('initial_addresses', settings.get('initial_addresses', DEFAULT_SETTINGS['initial_addresses'])))
            gap_limit = int(request.form.get('gap_limit', DEFAULT_SETTINGS['gap']))

            try:
                add_extended_public_key(
                    extended_key=extended_key,
                    gap_limit=gap_limit,
                    initial_addresses=initial_addresses,
                    label=label,
                    derivation_path=derivation_path,
                    start_index=start_index,
                )
                flash('Extended key added successfully!', 'success')
                return redirect(url_for('main.addresses'))
            except ValueError as e:
                flash(f'Error adding extended key: {str(e)}', 'danger')

    # Get settings for default gap limit
    settings = get_settings()

    return render_template('add_address.html', settings=settings)

@main_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings page."""
    if request.method == 'POST':
        # Update settings
        new_settings = {
            'check_interval': int(request.form.get('check_interval', DEFAULT_SETTINGS['check_interval'])),
            'use_self_hosted': request.form.get('use_self_hosted') == 'on',
            'node_url': request.form.get('node_url', DEFAULT_SETTINGS['node_url']),
            'node_port': int(request.form.get('node_port', DEFAULT_SETTINGS['node_port'])),
            'discord_webhook': request.form.get('discord_webhook', ''),
            'gap': int(request.form.get('gap', DEFAULT_SETTINGS['gap'])),
            'initial_addresses': int(request.form.get('initial_addresses', DEFAULT_SETTINGS['initial_addresses']))
        }

        try:
            update_settings(new_settings)
            flash('Settings updated successfully!', 'success')
            return redirect(url_for('main.settings'))
        except ValueError as e:
            flash(f'Error updating settings: {str(e)}', 'danger')

    # Get current settings
    settings = get_settings()
    return render_template('settings.html', settings=settings)

@main_bp.route('/api/delete_address/<address>')
def api_delete_address(address):
    """API endpoint to delete an address."""
    try:
        delete_address(address)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main_bp.route('/api/delete_extended_key/<key>')
def api_delete_extended_key(key):
    """API endpoint to delete an extended key."""
    try:
        delete_extended_key(key)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main_bp.route('/api/delete_extended_key_derivation_path/<key>/<path:derivation_path>')
def api_delete_extended_key_derivation_path(key, derivation_path):
    """API endpoint to delete a specific derivation path for an extended key."""
    try:
        delete_extended_key_derivation_path(key, derivation_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main_bp.route('/api/refresh_address/<address>')
def api_refresh_address(address):
    """API endpoint to manually refresh an address."""
    try:
        result = refresh_address(address)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main_bp.route('/api/update_gap_limit/<key>/<path:derivation_path>', methods=['POST'])
def api_update_gap_limit(key, derivation_path):
    """API endpoint to update the gap limit for a specific derivation path."""
    try:
        new_gap_limit = int(request.json.get('gap_limit', DEFAULT_SETTINGS['gap']))
        if new_gap_limit < 1:
            return jsonify({'success': False, 'error': 'Gap limit must be at least 1'})

        from app.services.extended_key_manager import update_gap_limit
        update_gap_limit(key, derivation_path, new_gap_limit)

        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'})

@main_bp.route('/api/validate_extended_key')
def api_validate_extended_key():
    """API endpoint to validate an extended public key."""
    key = request.args.get('key', '')
    is_valid = is_valid_extended_key(key)
    return jsonify({'valid': is_valid})

@main_bp.route('/api/test_connection')
def api_test_connection():
    """API endpoint to test the mempool API connection."""

    try:
        result = mempool_api.test_api_connection()
        if result:
            return jsonify({'success': True, 'message': 'Connection successful!'})
        else:
            return jsonify({'success': False, 'message': 'Connection failed. Check URL and port.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error testing connection: {str(e)}'})
