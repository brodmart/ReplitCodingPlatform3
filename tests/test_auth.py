import pytest
from flask import url_for, session
from werkzeug.security import generate_password_hash
from models import User

def test_register_view(client):
    """Test registration page loads correctly"""
    response = client.get('/auth/register')
    assert response.status_code == 200
    assert b'Register' in response.data

def test_successful_registration(client, app):
    """Test user registration with valid data"""
    response = client.post('/auth/register', data={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'SecurePass123!',
        'password_confirm': 'SecurePass123!'
    }, follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        user = User.query.filter_by(username='testuser').first()
        assert user is not None
        assert user.email == 'test@example.com'

def test_login_view(client):
    """Test login page loads correctly"""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'Login' in response.data

def test_successful_login(client, app):
    """Test login with valid credentials"""
    # Create test user
    with app.app_context():
        user = User(
            username='testuser',
            email='test@example.com',
            password_hash=generate_password_hash('SecurePass123!')
        )
        db.session.add(user)
        db.session.commit()

    # Attempt login
    response = client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'SecurePass123!'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert '_user_id' in sess

def test_logout(client, app):
    """Test logout functionality"""
    # First login
    client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'SecurePass123!'
    })
    
    # Then logout
    response = client.get('/auth/logout', follow_redirects=True)
    assert response.status_code == 200
    
    with client.session_transaction() as sess:
        assert '_user_id' not in sess

def test_invalid_login(client):
    """Test login with invalid credentials"""
    response = client.post('/auth/login', data={
        'username': 'nonexistent',
        'password': 'WrongPass123!'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data
