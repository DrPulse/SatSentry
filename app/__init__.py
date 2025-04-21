"""
Flask application initialization for SatSentry.
"""

import os
from datetime import datetime
from flask import Flask

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Configure the app
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-for-development-only')

    # Add template functionsz
    @app.context_processor
    def utility_processor():
        return {
            'now': datetime.now
        }

    # Register blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    # Scheduler will be initialized in main.py

    return app
