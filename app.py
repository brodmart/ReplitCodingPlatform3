import os
import logging
import eventlet
eventlet.monkey_patch()  # This needs to be at the very top after imports

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize SQLAlchemy with a custom base class
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate = Migrate()
csrf = CSRFProtect()
socketio = SocketIO()

def create_app():
    """Application factory function"""
    app = Flask(__name__)

    # Configure the Flask application
    app.config.update({
        'SECRET_KEY': os.environ.get('FLASK_SECRET_KEY', 'dev_key_for_development_only'),
        'SQLALCHEMY_DATABASE_URI': os.environ.get('DATABASE_URL'),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'pool_size': 5,
            'pool_recycle': 1800,
            'pool_pre_ping': True
        },
        'WTF_CSRF_ENABLED': True
    })

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Initialize Socket.IO with minimal configuration
    socketio.init_app(app, 
                     cors_allowed_origins="*",
                     async_mode='eventlet')

    # Import models here to ensure they're registered with SQLAlchemy
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}")
            raise

    @app.route('/')
    def index():
        return render_template('index.html', 
                             title='Ontario Secondary Computer Science Curriculum',
                             lang='en')  # Default to English

    # SocketIO event handlers
    @socketio.on('connect')
    def handle_connect():
        logger.info("Client connected")
        emit('connected', {'data': 'Connected'})

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info("Client disconnected")

    @socketio.on('compile_and_run')
    def handle_compile_and_run(data):
        try:
            code = data.get('code', '')
            logger.info(f"Received code to compile and run: {len(code)} bytes")
            # For now, just echo back the code
            emit('output', {
                'success': True,
                'session_id': 'test_session',
                'output': 'Hello from the server!\n',
                'waiting_for_input': True
            })
        except Exception as e:
            logger.error(f"Error in compile_and_run: {str(e)}")
            emit('error', {'message': str(e)})

    @socketio.on('input')
    def handle_input(data):
        try:
            session_id = data.get('session_id')
            user_input = data.get('input', '')
            logger.info(f"Received input for session {session_id}: {user_input}")
            # Echo back the input
            emit('output', {
                'success': True,
                'session_id': session_id,
                'output': f"You entered: {user_input}\n",
                'waiting_for_input': False
            })
        except Exception as e:
            logger.error(f"Error in handle_input: {str(e)}")
            emit('error', {'message': str(e)})

    return app

# Create the application instance
app = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=True, log_output=True)