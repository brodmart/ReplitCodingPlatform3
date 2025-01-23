import os
import logging
import eventlet
eventlet.monkey_patch()  # This needs to be at the very top after imports

from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, disconnect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase
from utils.socketio_logger import log_socket_event, track_connection, track_session
import time
import queue
import threading
import json

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize SQLAlchemy with a custom base class
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate = Migrate()
csrf = CSRFProtect()

# Initialize Socket.IO with detailed logging
socketio = SocketIO(
    logger=True,
    engineio_logger=True,
    cors_allowed_origins="*",
    async_mode='eventlet',
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e8,
    manage_session=True
)

# Store active console sessions
console_sessions = {}

class ConsoleSession:
    def __init__(self, session_id):
        self.session_id = session_id
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.active = True
        self.current_foreground_color = 'Gray'
        self.current_background_color = 'Black'
        self.cursor_position = {'x': 0, 'y': 0}
        self.lock = threading.Lock()
        logger.info(f"Created new console session: {session_id}")

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
        'WTF_CSRF_ENABLED': True,
        'SESSION_TYPE': 'filesystem',
        'PERMANENT_SESSION_LIFETIME': 1800,
    })

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    socketio.init_app(app)

    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}")
            raise

    @app.route('/')
    def index():
        logger.debug("Rendering index page")
        return render_template('index.html',
                             title='Ontario Secondary Computer Science Curriculum',
                             lang='en')

    @socketio.on('connect')
    @log_socket_event
    def handle_connect():
        """Handle client connection with enhanced tracking"""
        try:
            client_info = {
                'sid': request.sid,
                'transport': request.args.get('transport', 'unknown'),
                'user_agent': request.headers.get('User-Agent', 'unknown'),
                'remote_addr': request.remote_addr
            }
            track_connection(connected=True, client_info=client_info)
            logger.info(f"Client connected: {json.dumps(client_info)}")

            # Send immediate connection acknowledgment
            emit('connected', {
                'status': 'success',
                'message': 'Connected to server',
                'sid': request.sid
            })
        except Exception as e:
            logger.error(f"Error in handle_connect: {str(e)}", exc_info=True)
            emit('error', {'message': 'Connection error', 'type': 'connection_error'})
            disconnect()

    @socketio.on('disconnect')
    @log_socket_event
    def handle_disconnect():
        """Handle client disconnection with cleanup"""
        try:
            sid = request.sid
            logger.info(f"Client disconnecting: {sid}")

            # Clean up any active sessions for this client
            if sid in console_sessions:
                session = console_sessions[sid]
                session.active = False
                logger.info(f"Cleaning up console session: {session.session_id}")
                del console_sessions[sid]

            track_connection(connected=False)
            logger.info(f"Client disconnected: {sid}")

        except Exception as e:
            logger.error(f"Error in handle_disconnect: {str(e)}", exc_info=True)

    @socketio.on('compile_and_run')
    @log_socket_event
    def handle_compile_and_run(data):
        """Handle code compilation and execution with proper session tracking"""
        try:
            code = data.get('code', '')
            if not code:
                raise ValueError("No code provided")

            sid = request.sid
            session_id = f"session_{int(time.time())}"
            logger.info(f"Starting compilation session {session_id} for client {sid}")

            # Create new console session
            console_session = ConsoleSession(session_id)
            console_sessions[sid] = console_session

            track_session(session_id, active=True, context={
                'code_length': len(code),
                'client_sid': sid
            })

            # Initialize console state
            emit('console_operation', {
                'operation': 'ResetColor',
                'session_id': session_id
            })

            # Start code execution
            emit('output', {
                'success': True,
                'session_id': session_id,
                'output': 'Initializing console...\n',
                'waiting_for_input': False
            })

            # Test console operations
            emit('console_operation', {
                'operation': 'SetForegroundColor',
                'color': 'Green',
                'session_id': session_id
            })

            emit('output', {
                'success': True,
                'session_id': session_id,
                'output': 'Console ready for input!\n',
                'waiting_for_input': True
            })

        except Exception as e:
            logger.error(f"Error in compile_and_run: {str(e)}", exc_info=True)
            emit('error', {
                'message': str(e),
                'type': 'compilation_error',
                'session_id': session_id if 'session_id' in locals() else None
            })
            if 'session_id' in locals():
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

            # Get console session
            sid = request.sid
            console_session = console_sessions.get(sid)
            if not console_session:
                raise ValueError("Invalid session ID")

            # Process input
            with console_session.lock:
                console_session.input_queue.put(user_input)

            # Echo input for testing
            emit('console_operation', {
                'operation': 'SetForegroundColor',
                'color': 'Yellow',
                'session_id': session_id
            })

            emit('output', {
                'success': True,
                'session_id': session_id,
                'output': f"You entered: {user_input}\n",
                'waiting_for_input': True
            })

        except Exception as e:
            logger.error(f"Error in handle_input: {str(e)}", exc_info=True)
            emit('error', {
                'message': str(e),
                'type': 'input_error',
                'session_id': session_id if 'session_id' in locals() else None
            })

    @socketio.on('console_command')
    @log_socket_event
    def handle_console_command(data):
        """Handle C# console commands"""
        try:
            session_id = data.get('session_id')
            command = data.get('command')

            if not session_id or not command:
                raise ValueError("Invalid command data")

            console_session = console_sessions.get(session_id)
            if not console_session:
                raise ValueError("Invalid session ID")

            with console_session.lock:
                if command['type'] == 'SetCursorPosition':
                    console_session.cursor_position = {
                        'x': command['x'],
                        'y': command['y']
                    }
                    emit('console_operation', {
                        'operation': 'SetCursorPosition',
                        'x': command['x'],
                        'y': command['y'],
                        'session_id': session_id
                    })

                elif command['type'] in ['SetForegroundColor', 'SetBackgroundColor']:
                    color_attr = 'current_foreground_color' if command['type'] == 'SetForegroundColor' else 'current_background_color'
                    setattr(console_session, color_attr, command['color'])
                    emit('console_operation', {
                        'operation': command['type'],
                        'color': command['color'],
                        'session_id': session_id
                    })

                elif command['type'] == 'Clear':
                    console_session.cursor_position = {'x': 0, 'y': 0}
                    emit('console_operation', {
                        'operation': 'Clear',
                        'session_id': session_id
                    })

        except Exception as e:
            logger.error(f"Error in handle_console_command: {str(e)}", exc_info=True)
            emit('error', {
                'message': str(e),
                'type': 'console_error',
                'session_id': session_id if session_id else None
            })

    return app

# Create the application instance
app = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)