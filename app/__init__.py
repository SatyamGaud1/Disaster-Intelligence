"""
Disaster Intelligence Flask Application Factory.
Initializes the Flask instance, blueprints, database connections, and configurations.
"""

from flask import Flask, jsonify, render_template
from app.config import config_by_name, DevelopmentConfig
from app.database import close_db, init_db
from app.routes.main import main_bp
from app.routes.api import api_bp


def create_app(config_name_or_obj=None) -> Flask:
    """Application factory for Disaster Intelligence Platform."""
    app = Flask(__name__)

    # Load configuration
    if isinstance(config_name_or_obj, str):
        config_class = config_by_name.get(config_name_or_obj, DevelopmentConfig)
        app.config.from_object(config_class)
    elif config_name_or_obj is not None:
        app.config.from_object(config_name_or_obj)
    else:
        app.config.from_object(DevelopmentConfig)

    # Register teardown function to close database connections
    app.teardown_appcontext(close_db)

    # Register Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    # Custom CLI Command: flask init-db
    @app.cli.command("init-db")
    def init_db_command():
        """Initialize and create all database tables."""
        init_db(app)
        print("Database schema successfully initialized.")

    # Error Handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({
            "status": "error",
            "code": 404,
            "message": "The requested resource was not found on this server."
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            "status": "error",
            "code": 500,
            "message": "An internal server error occurred."
        }), 500

    return app

