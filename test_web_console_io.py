import unittest
import logging
import time
import tempfile
from pathlib import Path
from compiler_service import (
    compile_and_run, start_interactive_session,
    send_input, get_output, CompilerSession,
    cleanup_session
)
from utils.compiler_logger import compiler_logger

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestWebConsoleIO(unittest.TestCase):
    """Test suite for web console I/O functionality"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp(prefix='test_console_')
        self.active_sessions = set()

    def tearDown(self):
        """Clean up test environment"""
        for session_id in self.active_sessions:
            try:
                logger.info(f"Cleaning up session {session_id}")
                cleanup_session(session_id)
                self.active_sessions.remove(session_id)
            except Exception as e:
                logger.error(f"Error cleaning up session {session_id}: {e}")
        try:
            if Path(self.temp_dir).exists():
                for file in Path(self.temp_dir).iterdir():
                    try:
                        file.unlink()
                    except Exception as e:
                        logger.error(f"Error removing file {file}: {e}")
                Path(self.temp_dir).rmdir()
        except Exception as e:
            logger.error(f"Error removing temp dir: {e}")

    def verify_interactive_session(self, code: str, language: str, test_cases: list) -> bool:
        """Helper method to verify interactive I/O sessions"""
        # Create session with stable ID
        session_id = f"test_interactive_{str(hash(code))}"
        compiler_logger.log_compilation_start(session_id, code)
        logger.info(f"Starting {language} interactive session")

        # Initialize session with temp directory
        session = CompilerSession(session_id, self.temp_dir)
        self.active_sessions.add(session_id)

        try:
            # Start interactive session
            result = start_interactive_session(session, code, language)
            if not result['success']:
                compiler_logger.log_compilation_error(
                    session_id,
                    Exception(result.get('error', 'Unknown error')),
                    {'stage': 'session_start'}
                )
                return False

            # Wait for process initialization
            time.sleep(1)
            compiler_logger.log_execution_state(session_id, 'session_started')
            logger.info(f"{language} session started successfully")

            # Process each test case
            for i, test_case in enumerate(test_cases, 1):
                logger.info(f"Running test case {i}/{len(test_cases)}")

                # Get initial output and verify prompt
                output = get_output(session_id)
                if not output['success']:
                    compiler_logger.log_runtime_error(
                        session_id,
                        "Failed to get initial output",
                        output
                    )
                    return False

                logger.info(f"Current output: {output.get('output', '')}")

                # Send input
                logger.info(f"Sending input: {test_case['input']}")
                send_result = send_input(session_id, test_case['input'])
                if not send_result['success']:
                    compiler_logger.log_runtime_error(
                        session_id,
                        "Failed to send input",
                        send_result
                    )
                    return False

                # Wait for processing
                time.sleep(0.5)

                # Get and verify output
                final_output = get_output(session_id)
                if not final_output['success']:
                    compiler_logger.log_runtime_error(
                        session_id,
                        "Failed to get output after input",
                        final_output
                    )
                    return False

                if test_case['expected'] not in final_output['output']:
                    compiler_logger.log_runtime_error(
                        session_id,
                        f"Expected output not found: {test_case['expected']}",
                        {'actual_output': final_output['output']}
                    )
                    return False

                time.sleep(0.5)  # Wait between test cases

            # Log successful completion
            compiler_logger.log_execution_state(session_id, 'test_completed', {
                'outputs_received': True,
                'test_success': True
            })
            return True

        except Exception as e:
            compiler_logger.log_runtime_error(session_id, str(e))
            logger.error(f"Error in verify_interactive_session: {str(e)}")
            return False

    def test_cpp_basic_io(self):
        """Test C++ basic input/output"""
        code = """
        #include <iostream>
        #include <string>
        using namespace std;

        int main() {
            string name;
            cout << "Enter your name: ";
            getline(cin, name);
            cout << "Hello, " << name << "!" << endl;
            return 0;
        }
        """
        test_cases = [
            {
                'input': 'John Doe',
                'expected': 'Hello, John Doe!'
            }
        ]
        self.assertTrue(
            self.verify_interactive_session(code, 'cpp', test_cases),
            "C++ basic I/O test failed"
        )

    def test_csharp_basic_io(self):
        """Test C# basic input/output"""
        code = """
        using System;

        class Program {
            static void Main() {
                Console.Write("Enter your name: ");
                string name = Console.ReadLine();
                Console.WriteLine($"Hello, {name}!");
            }
        }
        """
        test_cases = [
            {
                'input': 'Jane Smith',
                'expected': 'Hello, Jane Smith!'
            }
        ]
        self.assertTrue(
            self.verify_interactive_session(code, 'csharp', test_cases),
            "C# basic I/O test failed"
        )

if __name__ == '__main__':
    unittest.main(verbosity=2)