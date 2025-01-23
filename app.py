import os
import logging
import eventlet
eventlet.monkey_patch()  # This needs to be at the very top after imports

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, disconnect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase
from utils.socketio_logger import log_socket_event, track_connection, track_session
import time

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

    # Initialize Socket.IO with enhanced configuration
    socketio.init_app(app,
                     cors_allowed_origins="*",
                     async_mode='eventlet',
                     ping_timeout=60,
                     ping_interval=25,
                     reconnection=True,
                     logger=True,
                     engineio_logger=True)

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
                             lang='en')

    # Enhanced SocketIO event handlers with proper error handling and logging
    @socketio.on('connect')
    @log_socket_event
    def handle_connect():
        """Handle client connection with enhanced tracking"""
        try:
            client_info = {
                'transport': request.args.get('transport', 'unknown'),
                'user_agent': request.headers.get('User-Agent', 'unknown')
            }
            track_connection(connected=True, client_info=client_info)
            emit('connected', {'status': 'success', 'message': 'Connected to server'})
            logger.info(f"Client connected with info: {client_info}")
        except Exception as e:
            logger.error(f"Error in handle_connect: {str(e)}")
            disconnect()

    @socketio.on('disconnect')
    @log_socket_event
    def handle_disconnect():
        """Handle client disconnection with cleanup"""
        try:
            track_connection(connected=False)
            logger.info("Client disconnected")
        except Exception as e:
            logger.error(f"Error in handle_disconnect: {str(e)}")

    @socketio.on('compile_and_run')
    @log_socket_event
    def handle_compile_and_run(data):
        """Handle code compilation and execution with proper session tracking"""
        try:
            code = data.get('code', '')
            session_id = f"session_{int(time.time())}"
            logger.info(f"Starting compilation session {session_id}")

            track_session(session_id, active=True, context={'code_length': len(code)})

            # For now, just echo back the code
            emit('output', {
                'success': True,
                'session_id': session_id,
                'output': 'Hello from the server!\n',
                'waiting_for_input': True
            })

        except Exception as e:
            logger.error(f"Error in compile_and_run: {str(e)}", exc_info=True)
            emit('error', {'message': str(e), 'type': 'compilation_error'})
            track_session(session_id, active=False)

    @socketio.on('input')
    @log_socket_event
    def handle_input(data):
        """Handle user input with enhanced error handling"""
        try:
            session_id = data.get('session_id')
            user_input = data.get('input', '')

            if not session_id:
                raise ValueError("No session ID provided")

            logger.info(f"Received input for session {session_id}: {user_input}")

            emit('output', {
                'success': True,
                'session_id': session_id,
                'output': f"You entered: {user_input}\n",
                'waiting_for_input': False
            })

        except Exception as e:
            logger.error(f"Error in handle_input: {str(e)}", exc_info=True)
            emit('error', {
                'message': str(e),
                'type': 'input_error',
                'session_id': session_id if session_id else None
            })

    return app

# Create the application instance
app = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=True, log_output=True)