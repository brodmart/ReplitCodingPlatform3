from flask import Blueprint

from .auth_routes import auth
from .activity_routes import activities

# Register all blueprints with unique names
auth.name = 'auth_blueprint'
activities.name = 'activities_blueprint'

# Export blueprints list
blueprints = [auth, activities]