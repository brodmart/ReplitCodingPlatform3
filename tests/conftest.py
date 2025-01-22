"""
Test configuration file that only loads during pytest execution.
"""
import os
import pytest
from flask import Flask
from database import db

def create_test_app():
    """Create a Flask app instance for testing"""
    app = Flask(__name__)
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost.localdomain'
    })

    return app

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_test_app()

    # Create tables for testing
    with app.app_context():
        db.init_app(app)
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()