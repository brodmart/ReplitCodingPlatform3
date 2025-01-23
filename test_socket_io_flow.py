import logging
import unittest
from flask import Flask
from flask_socketio import SocketIO, emit
from flask.testing import FlaskClient
from unittest.mock import patch
import eventlet
eventlet.monkey_patch()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestSocketIOFlow(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app)
        self.client = self.app.test_client()

        # Track events and state
        self.events = []
        self.waiting_for_input = False
        self.last_session_id = None
        self.input_received = False
        self.output_sent = False

        @self.socketio.on('connect')
        def handle_connect():
            logger.info("Client connected")
            self.events.append(('connect', None))

        @self.socketio.on('compile_and_run')
        def handle_compile_run(data):
            logger.info(f"Received compile_and_run: {data}")
            self.events.append(('compile_and_run', data))

            # Track session state
            self.last_session_id = 'test_session'

            # Emit compilation success with session ID
            logger.info("Emitting compilation_success")
            self.socketio.emit('compilation_success', {'session_id': self.last_session_id})

            # Emit initial output with waiting_for_input
            logger.info("Emitting initial output")
            self.socketio.emit('output', {
                'session_id': self.last_session_id,
                'output': 'Enter your name:',
                'waiting_for_input': True
            })
            self.waiting_for_input = True
            self.output_sent = True

        @self.socketio.on('input')
        def handle_input(data):
            logger.info(f"Received input: {data}")
            self.events.append(('input', data))

            # Verify session ID matches
            if data.get('session_id') != self.last_session_id:
                logger.error(f"Session ID mismatch: expected {self.last_session_id}, got {data.get('session_id')}")
                return

            self.input_received = True
            input_text = data.get('input', '')

            # Process input and emit response
            logger.info(f"Processing input and emitting response for: {input_text}")
            self.socketio.emit('output', {
                'session_id': self.last_session_id,
                'output': f"Hello, {input_text}!",
                'waiting_for_input': False
            })
            self.waiting_for_input = False
            self.output_sent = True

    def test_input_output_cycle(self):
        """Test complete input/output cycle with detailed state tracking"""
        client = self.socketio.test_client(self.app)

        # Test connection
        self.assertTrue(client.is_connected())
        logger.info("Client connected successfully")

        # Send compile request
        test_code = '''
        using System;
        class Program {
            static void Main() {
                Console.WriteLine("Enter your name:");
                string name = Console.ReadLine();
                Console.WriteLine($"Hello, {name}!");
            }
        }
        '''
        client.emit('compile_and_run', {'code': test_code})
        logger.info("Sent compile_and_run request")

        # Verify compilation success and initial prompt
        responses = client.get_received()
        logger.info(f"Received responses after compilation: {responses}")

        # Check if session ID was received
        self.assertIsNotNone(self.last_session_id)
        self.assertTrue(self.output_sent)
        self.assertTrue(self.waiting_for_input)

        # Send input
        test_input = 'Test User'
        client.emit('input', {
            'session_id': self.last_session_id,
            'input': test_input
        })
        logger.info("Sent input")

        # Check final response
        responses = client.get_received()
        logger.info(f"Received responses after input: {responses}")

        # Verify complete cycle
        self.assertTrue(self.input_received)
        self.assertTrue(self.output_sent)
        self.assertFalse(self.waiting_for_input)

        # Verify event sequence
        expected_events = [('connect', None), 
                         ('compile_and_run', {'code': test_code}), 
                         ('input', {'session_id': self.last_session_id, 'input': test_input})]
        self.assertEqual(self.events, expected_events)

if __name__ == '__main__':
    unittest.main()