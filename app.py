import os
import logging
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from compiler_service import start_interactive_session, get_output, send_input, cleanup_session, get_or_create_session

# Basic logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev_key')
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('compile_and_run')
def handle_compile_and_run(data):
    try:
        code = data.get('code', '')
        logger.info("Received code to compile:")
        logger.info("-" * 40)
        logger.info(code)
        logger.info("-" * 40)

        if not code:
            emit('output', {'success': False, 'error': 'No code provided'})
            return

        session = get_or_create_session()
        result = start_interactive_session(session, code, 'csharp')

        if result['success']:
            # Get initial output
            output_result = get_output(session.session_id)
            emit('output', {
                'success': True,
                'output': output_result.get('output', ''),
                'waiting_for_input': output_result.get('waiting_for_input', False),
                'session_id': session.session_id
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
def handle_send_input(data):
    try:
        session_id = data.get('session_id')
        input_text = data.get('input', '')
        logger.info(f"Received input for session {session_id}: {input_text!r}")

        if not session_id or not input_text:
            emit('output', {'success': False, 'error': 'Invalid input data'})
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

@socketio.on('disconnect')
def handle_disconnect():
    try:
        if 'session_id' in session:
            cleanup_session(session['session_id'])
    except Exception as e:
        logger.error(f"Error in disconnect: {e}")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)