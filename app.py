# Eventlet monkey patch must be the first import
import eventlet
eventlet.monkey_patch(socket=True, select=True)

import os
import logging
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

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Starting application initialization...")

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
        self.waiting_for_input = False
        self.current_foreground_color = 'Gray'
        self.current_background_color = 'Black'
        self.cursor_position = {'x': 0, 'y': 0}
        self.lock = threading.Lock()
        self.compilation_complete = False
        logger.info(f"Created new console session: {session_id} (active: {self.active})")

    def activate(self):
        with self.lock:
            self.active = True
            logger.info(f"Activated session: {self.session_id}")

    def deactivate(self):
        with self.lock:
            self.active = False
            logger.info(f"Deactivated session: {self.session_id}")

    def set_compilation_complete(self):
        with self.lock:
            self.compilation_complete = True
            logger.info(f"Compilation complete for session: {self.session_id}")

    def is_active_and_ready(self):
        with self.lock:
            ready = self.active and self.compilation_complete
            logger.debug(f"Session {self.session_id} status - active: {self.active}, ready: {ready}")
            return ready

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
        """Handle index page with enhanced logging"""
        try:
            logger.info("Starting index page render")
            logger.debug("Rendering index page with template parameters: " + 
                        "title='Ontario Secondary Computer Science Curriculum', lang='en'")

            rendered = render_template('index.html',
                                      title='Ontario Secondary Computer Science Curriculum',
                                      lang='en')
            logger.info("Successfully rendered index page")
            return rendered
        except Exception as e:
            logger.error(f"Error rendering index page: {str(e)}", exc_info=True)
            return "Error loading page", 500

    @socketio.on('connect')
    @log_socket_event
    def handle_connect(auth=None):
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
    def handle_disconnect(reason=None):
        """Handle client disconnection with cleanup"""
        try:
            sid = request.sid
            logger.info(f"Client disconnecting: {sid}")

            # Clean up any active sessions for this client
            if sid in console_sessions:
                session = console_sessions[sid]
                session.deactivate()
                with session.lock:
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
        request_start = time.time()
        logger.info(f"[REQUEST] Starting compile_and_run request at {request_start}")

        try:
            code = data.get('code', '')
            if not code:
                logger.error("[COMPILE] No code provided in compile_and_run request")
                raise ValueError("No code provided")

            sid = request.sid
            session_id = f"session_{int(time.time())}"
            logger.info(f"[COMPILE] Starting compilation for session {session_id} client {sid}")
            logger.debug(f"[COMPILE] Code length: {len(code)}, First line: {code.split()[0]}")

            # Create new console session with proper activation
            logger.info(f"[SESSION] Creating new console session {session_id}")
            console_session = ConsoleSession(session_id)
            with console_session.lock:
                if sid in console_sessions:
                    old_session = console_sessions[sid]
                    logger.warning(f"[SESSION] Cleaning up existing session for client {sid}")
                    old_session.deactivate()
                console_sessions[sid] = console_session
                console_session.activate()
                logger.info(f"[SESSION] Created and activated console session {session_id}")

            track_session(session_id, active=True, context={
                'code_length': len(code),
                'client_sid': sid,
                'timestamp': time.time()
            })

            # Import necessary C# compilation module with validation
            try:
                from compiler_service import compile_and_run
                logger.info(f"[COMPILE] Successfully imported compiler_service for session {session_id}")
            except ImportError as e:
                logger.error(f"[COMPILE] Failed to import compiler_service: {str(e)}")
                emit('output', {
                    'success': False,
                    'session_id': session_id,
                    'output': f"Compiler service unavailable: {str(e)}\n",
                    'waiting_for_input': False
                })
                return

            # Immediate acknowledgment of compilation start
            logger.debug(f"[COMPILE] Sending initial acknowledgment for session {session_id}")
            emit('output', {
                'success': True,
                'session_id': session_id,
                'output': 'Compiling and running code...\n',
                'waiting_for_input': False
            })

            # Reset console state
            logger.debug(f"[COMPILE] Resetting console state for session {session_id}")
            emit('console_operation', {
                'operation': 'Clear',
                'session_id': session_id
            })

            # Start C# compilation and execution with detailed logging and timeouts
            logger.info(f"[COMPILE] Starting C# compilation process for session {session_id}")
            compilation_start_time = time.time()

            try:
                # Set a timeout for compilation
                with eventlet.Timeout(30, exception=eventlet.Timeout):  # 30 second timeout
                    logger.debug(f"[COMPILE] Initiating compilation for session {session_id}")
                    compilation_result = compile_and_run(code, 'csharp', session_id)
                    logger.debug(f"[COMPILE] Raw compilation result: {compilation_result}")

                compilation_duration = time.time() - compilation_start_time
                logger.info(f"[COMPILE] Compilation completed in {compilation_duration:.2f}s for session {session_id}")

                # Set compilation complete and process result with proper synchronization
                with console_session.lock:
                    console_session.set_compilation_complete()
                    logger.debug(f"[COMPILE] Set compilation complete for {session_id}")

                    if compilation_result.get('success'):
                        waiting_for_input = compilation_result.get('waiting_for_input', False)
                        console_session.waiting_for_input = waiting_for_input
                        logger.info(f"[COMPILE] Session {session_id} waiting for input: {waiting_for_input}")

                        output = compilation_result.get('output', '')
                        if output:
                            logger.info(f"[COMPILE] Emitting output for {session_id}: {repr(output)}")
                            emit('output', {
                                'success': True,
                                'session_id': session_id,
                                'output': output + ('\n' if not output.endswith('\n') else ''),
                                'waiting_for_input': waiting_for_input
                            })
                    else:
                        error = compilation_result.get('error', 'Unknown compilation error')
                        logger.error(f"[COMPILE] Error in session {session_id}: {error}")
                        emit('output', {
                            'success': False,
                            'session_id': session_id,
                            'output': f"Compilation error: {error}\n",
                            'waiting_for_input': False
                        })

            except eventlet.Timeout:
                logger.error(f"[COMPILE] Compilation timeout after {time.time() - compilation_start_time:.2f}s for session {session_id}")
                emit('output', {
                    'success': False,
                    'session_id': session_id,
                    'output': "Compilation timed out after 30 seconds\n",
                    'waiting_for_input': False
                })
                return

            except Exception as e:
                logger.error(f"[COMPILE] Compilation failed for session {session_id}: {str(e)}", exc_info=True)
                emit('output', {
                    'success': False,
                    'session_id': session_id,
                    'output': f"Compilation failed: {str(e)}\n",
                    'waiting_for_input': False
                })
                return

            finally:
                request_duration = time.time() - request_start
                logger.info(f"[REQUEST] compile_and_run request completed in {request_duration:.2f}s")

        except Exception as e:
            logger.error(f"[COMPILE] Critical error in compile_and_run: {str(e)}", exc_info=True)
            emit('error', {
                'message': str(e),
                'type': 'compilation_error',
                'session_id': session_id if 'session_id' in locals() else None
            })
            if 'session_id' in locals():
                track_session(session_id, active=False, error=str(e))

    @socketio.on('input')
    @log_socket_event
    def handle_input(data):
        """Handle user input with enhanced error handling and session synchronization"""
        try:
            session_id = data.get('session_id')
            user_input = data.get('input', '')

            if not session_id:
                raise ValueError("No session ID provided")

            logger.info(f"Received input for session {session_id}: {user_input}")

            # Get console session with proper locking
            sid = request.sid
            console_session = console_sessions.get(sid)
            if not console_session:
                logger.error(f"Session {session_id} not found for client {sid}")
                raise ValueError("Invalid session ID or session expired")

            if not console_session.is_active_and_ready():
                logger.error(f"Session {session_id} not active or not ready")
                raise ValueError("Session not active or compilation not complete")

            with console_session.lock:
                if not console_session.waiting_for_input:
                    logger.error(f"Session {session_id} not waiting for input")
                    raise ValueError("Session not waiting for input")

                # Process input through C# runtime
                from compiler_service import process_csharp_input

                # Send input to C# program with proper synchronization
                result = process_csharp_input(session_id, user_input)
                logger.info(f"Process input result for session {session_id}: {result}")

                if result.get('success'):
                    console_session.waiting_for_input = result.get('waiting_for_input', False)
                    logger.info(f"Session {session_id} waiting for input updated to: {console_session.waiting_for_input}")

                    # Enhanced output handling
                    output = result.get('output', '')
                    emit('output', {
                        'success': True,
                        'session_id': session_id,
                        'output': output + ('\n' if output else ''),
                        'waiting_for_input': console_session.waiting_for_input
                    })
                else:
                    error_msg = result.get('error', 'Failed to process input')
                    logger.error(f"Input processing error in session {session_id}: {error_msg}")
                    emit('error', {
                        'message': error_msg,
                        'type': 'input_error',
                        'session_id': session_id
                    })

        except ValueError as ve:
            logger.error(f"Validation error in handle_input: {str(ve)}")
            emit('error', {
                'message': str(ve),
                'type': 'input_error',
                'session_id': session_id if 'session_id' in locals() else None
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
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=True,
        log_output=True
    )