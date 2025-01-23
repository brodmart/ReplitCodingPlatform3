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
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

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
        code = data.get('code', '')
        logger.info("Received code to compile:")
        logger.info("-" * 40)
        logger.info(code)
        logger.info("-" * 40)

        if not code:
            emit('output', {'success': False, 'error': 'No code provided'})
            return

        interactive_session = get_or_create_session()
        result = start_interactive_session(interactive_session, code, 'csharp')

        if result['success']:
            session['session_id'] = interactive_session.session_id
            track_session(interactive_session.session_id, active=True)

            # Get initial output
            output_result = get_output(interactive_session.session_id)
            emit('output', {
                'success': True,
                'output': output_result.get('output', ''),
                'waiting_for_input': output_result.get('waiting_for_input', False),
                'session_id': interactive_session.session_id
            })
        else:
            logger.error(f"Compilation failed: {result.get('error')}")
            emit('output', {
                'success': False, 
                'error': result.get('error', 'Compilation failed')
            })

    except Exception as e:
        logger.error(f"Error in compile_and_run: {e}")
        emit('output', {
            'success': False,
            'error': f"Server error: {e}"
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
        logger.error(f"Error in send_input: {e}")
        emit('output', {
            'success': False,
            'error': f"Server error: {e}"
        })

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)