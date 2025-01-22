import logging
from typing import Dict
from flask import Flask, Blueprint
from werkzeug.routing import MapAdapter

logger = logging.getLogger(__name__)

class BlueprintValidator:
    """Validates blueprint registration and essential routes"""

    def __init__(self, app: Flask):
        self.app = app
        self.url_map: MapAdapter = app.url_map
        self.essential_routes = {
            'auth.login': '/auth/login',
            'auth.register': '/auth/register',
            'auth.logout': '/auth/logout',
            'static_pages.index': '/'
        }

    def validate_blueprints(self) -> Dict[str, bool]:
        """Validate that all required blueprints are registered"""
        required_blueprints = {'auth', 'static_pages', 'activities', 'tutorial'}
        registered_blueprints = set(self.app.blueprints.keys())

        validation_results = {}
        for blueprint in required_blueprints:
            is_registered = blueprint in registered_blueprints
            validation_results[blueprint] = is_registered
            if not is_registered:
                logger.error(f"Required blueprint '{blueprint}' is not registered")
            else:
                logger.debug(f"Blueprint '{blueprint}' is properly registered")

        return validation_results

    def validate_essential_routes(self) -> Dict[str, bool]:
        """Validate that all essential routes are accessible"""
        validation_results = {}

        for endpoint, path in self.essential_routes.items():
            try:
                self.app.url_map.bind('').match(path)
                validation_results[endpoint] = True
                logger.debug(f"Essential route '{endpoint}' ({path}) is accessible")
            except Exception as e:
                validation_results[endpoint] = False
                logger.error(f"Essential route '{endpoint}' ({path}) is not accessible: {str(e)}")

        return validation_results

def validate_app_configuration(app: Flask) -> bool:
    """Validate critical application configuration"""
    required_config = {
        'SECRET_KEY': 'Security risk: Secret key not set',
        'SQLALCHEMY_DATABASE_URI': 'Database configuration missing',
        'SESSION_TYPE': 'Session configuration missing'
    }

    is_valid = True

    for config_key, error_message in required_config.items():
        if not app.config.get(config_key):
            logger.error(f"Configuration error: {error_message}")
            is_valid = False
        else:
            logger.debug(f"Configuration '{config_key}' is properly set")

    return is_valid