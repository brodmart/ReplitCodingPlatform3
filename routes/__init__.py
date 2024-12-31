from flask import Blueprint

from .auth_routes import auth
from .activity_routes import activities

# Register all blueprints
blueprints = [auth, activities]