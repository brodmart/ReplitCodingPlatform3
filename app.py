import os
import logging
from flask import Flask, render_template
from flask_socketio import SocketIO
from compiler_service import compile_and_run, send_input, get_output, cleanup_session
from utils.socketio_logger import log_socket_event, track_connection, track_session

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask and SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY", "dev_key_for_development_only")
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

@app.route('/')
def index():
    """Render the main activity page"""
    return render_template('activity.html')

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    track_connection(connected=True)
    logger.info("Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    track_connection(connected=False)
    logger.info("Client disconnected")

@socketio.on('compile_and_run')
@log_socket_event
def handle_compile_and_run(data):
    """Handle code compilation and execution"""
    if not data or 'code' not in data:
        logger.error("No code provided in compile_and_run request")
        socketio.emit('error', {'message': 'No code provided'})
        return

    try:
        logger.debug(f"Starting compilation for code: {data['code'][:100]}...")
        result = compile_and_run(data['code'], 'csharp')

        if not result.get('success'):
            error_msg = result.get('error', 'Compilation failed')
            logger.error(f"Compilation error: {error_msg}")
            socketio.emit('compilation_error', {'error': error_msg})
            return

        session_id = result.get('session_id')
        if not session_id:
            logger.error("No session ID returned from compilation")
            socketio.emit('error', {'message': 'Failed to create session'})
            return

        track_session(session_id, active=True)
        logger.info(f"Compilation successful, session ID: {session_id}")
        socketio.emit('compilation_success', {'session_id': session_id})

        # Get initial output
        output = get_output(session_id)
        if output and output.get('success'):
            waiting_for_input = output.get('waiting_for_input', False)
            logger.info(f"Initial output received, waiting_for_input: {waiting_for_input}")
            socketio.emit('output', {
                'session_id': session_id,
                'output': output.get('output', ''),
                'waiting_for_input': waiting_for_input
            })
        else:
            logger.error("Failed to get initial program output")
            socketio.emit('error', {'message': 'Failed to get program output'})

    except Exception as e:
        logger.error(f"Compilation error: {str(e)}", exc_info=True)
        socketio.emit('error', {'message': str(e)})

@socketio.on('input')
@log_socket_event
def handle_input(data):
    """Handle console input"""
    session_id = data.get('session_id')
    input_text = data.get('input')

    if not session_id or input_text is None:
        logger.error(f"Invalid input request: session_id={session_id}, input={input_text}")
        socketio.emit('error', {'message': 'Invalid session or input'})
        return

    try:
        logger.debug(f"Sending input '{input_text}' to session {session_id}")
        result = send_input(session_id, input_text + '\n')

        if not result or not result.get('success'):
            logger.error(f"Failed to send input to session {session_id}")
            socketio.emit('error', {'message': 'Failed to send input'})
            return

        logger.debug(f"Input sent successfully to session {session_id}")

        # Get program output after input
        output = get_output(session_id)
        if output and output.get('success'):
            waiting_for_input = output.get('waiting_for_input', False)
            logger.info(f"Output received after input, waiting_for_input: {waiting_for_input}")
            socketio.emit('output', {
                'session_id': session_id,
                'output': output.get('output', ''),
                'waiting_for_input': waiting_for_input
            })
        else:
            logger.error(f"Failed to get output after input for session {session_id}")
            socketio.emit('error', {'message': 'Failed to get output'})

    except Exception as e:
        logger.error(f"Input handling error: {str(e)}", exc_info=True)
        socketio.emit('error', {'message': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=True, log_output=True)