import os
import logging
from flask import Flask, render_template, session
from flask_socketio import SocketIO, emit
from compiler_service import start_interactive_session, get_output, send_input, cleanup_session, get_or_create_session
from utils.socketio_logger import log_socket_event, track_connection, track_session, log_error

# Enhanced logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev_key')
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True, ping_timeout=5)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """Handle new socket connection with tracking"""
    try:
        track_connection(connected=True, client_info=session.get('client_info'))
        logger.info("New client connected")
    except Exception as e:
        log_error("connection_error", str(e))
        logger.error(f"Error in connect: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle socket disconnection with cleanup"""
    try:
        if 'session_id' in session:
            cleanup_session(session['session_id'])
            track_session(session['session_id'], active=False)
            session.pop('session_id', None)
        track_connection(connected=False)
        logger.info("Client disconnected")
    except Exception as e:
        log_error("disconnect_error", str(e))
        logger.error(f"Error in disconnect: {e}")

@socketio.on('compile_and_run')
@log_socket_event
def handle_compile_and_run(data):
    """Handle code compilation and execution with enhanced logging"""
    try:
        logger.info("Received compile_and_run request")
        code = data.get('code', '')

        if not code:
            logger.warning("No code provided in compile_and_run request")
            emit('output', {'success': False, 'error': 'No code provided'})
            return

        logger.info(f"Creating new session for compilation")
        interactive_session = get_or_create_session()

        logger.info(f"Starting interactive session with id: {interactive_session.session_id}")
        result = start_interactive_session(interactive_session, code, 'csharp')

        logger.info(f"Interactive session result: {result}")

        if result['success']:
            # Store session ID in Flask session
            session['session_id'] = interactive_session.session_id
            track_session(interactive_session.session_id, active=True)

            logger.info(f"Getting initial output for session: {interactive_session.session_id}")
            output_result = get_output(interactive_session.session_id)

            logger.info(f"Emitting output result: {output_result}")
            emit('output', {
                'success': True,
                'output': output_result.get('output', ''),
                'waiting_for_input': output_result.get('waiting_for_input', False),
                'session_id': interactive_session.session_id
            })
        else:
            error_msg = result.get('error', 'Compilation failed')
            logger.error(f"Compilation failed: {error_msg}")
            emit('output', {
                'success': False, 
                'error': error_msg
            })

    except Exception as e:
        logger.error(f"Error in compile_and_run: {e}", exc_info=True)
        emit('output', {
            'success': False,
            'error': f"Server error: {str(e)}"
        })

@socketio.on('send_input')
@log_socket_event
def handle_send_input(data):
    """Handle user input with validation and logging"""
    try:
        session_id = data.get('session_id')
        input_text = data.get('input', '')
        logger.info(f"Received input for session {session_id}: {input_text!r}")

        if not session_id or not input_text:
            emit('output', {'success': False, 'error': 'Invalid input data'})
            return

        if session.get('session_id') != session_id:
            emit('output', {'success': False, 'error': 'Invalid session'})
            return

        result = send_input(session_id, input_text)
        if result['success']:
            output_result = get_output(session_id)
            logger.info(f"Got output after input: {output_result.get('output', '')!r}")
            emit('output', {
                'success': True,
                'output': output_result.get('output', ''),
                'waiting_for_input': output_result.get('waiting_for_input', False)
            })
        else:
            emit('output', {'success': False, 'error': result['error']})

    except Exception as e:
        logger.error(f"Error in send_input: {e}", exc_info=True)
        emit('output', {
            'success': False,
            'error': f"Server error: {e}"
        })

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=True, log_output=True)