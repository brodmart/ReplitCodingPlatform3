import unittest
import logging
import time
import uuid
import tempfile
from pathlib import Path
from compiler_service import (
    compile_and_run, start_interactive_session,
    send_input, get_output, get_or_create_session,
    cleanup_session, CompilerSession
)

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
            cleanup_session(session_id)
        Path(self.temp_dir).rmdir()

    def verify_interactive_session(self, code: str, language: str, test_cases: list) -> bool:
        """Verify interactive I/O session with multiple test cases"""
        logger.info(f"Testing {language} interactive session with {len(test_cases)} test cases")

        # Start session
        session_id = str(uuid.uuid4())
        session = CompilerSession(session_id, self.temp_dir)
        self.active_sessions.add(session_id)

        result = start_interactive_session(session, code, language)
        self.assertTrue(result['success'], f"Failed to start {language} session")
        self.assertTrue(result['interactive'], "Session should be interactive")

        try:
            # Process each test case
            for i, test_case in enumerate(test_cases):
                logger.info(f"Running test case {i + 1}/{len(test_cases)}")

                # Get current output
                output = self._get_output_with_retry(session_id)
                self.assertTrue(output['success'], f"Failed to get output for case {i}")
                self.assertTrue(output.get('waiting_for_input', False),
                              f"{language} program not waiting for input as expected")

                # Send input
                logger.info(f"Sending input: {test_case['input']}")
                input_result = send_input(session_id, test_case['input'])
                self.assertTrue(input_result['success'], f"Failed to send input for case {i}")

                # Verify output
                final_output = self._get_output_with_retry(session_id, 
                                                       expected=test_case['expected'])
                self.assertTrue(final_output['success'], 
                              f"Failed to get final output for case {i}")
                self.assertIn(test_case['expected'], final_output['output'],
                           f"Expected '{test_case['expected']}' not found in output")

            return True
        except Exception as e:
            logger.error(f"Error in verify_interactive_session: {str(e)}")
            return False
        finally:
            cleanup_session(session_id)

    def _get_output_with_retry(self, session_id: str, expected: str = None, 
                             max_retries: int = 3, retry_delay: float = 0.5) -> dict:
        """Get output with retries and proper error handling"""
        for retry in range(max_retries):
            try:
                time.sleep(retry_delay)
                output = get_output(session_id)

                # Check if we got the expected output
                if output['success'] and (expected is None or expected in output['output']):
                    return output

                if not output['success'] and 'Process not running' in output.get('error', ''):
                    break

            except Exception as e:
                logger.error(f"Error getting output (retry {retry}): {e}")

            time.sleep(retry_delay)

        return get_output(session_id)  # Return last attempt result

    def test_cpp_basic_io(self):
        """Test C++ basic input/output interactions"""
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
        self.verify_interactive_session(code, 'cpp', test_cases)

    def test_cpp_multiple_inputs(self):
        """Test C++ multiple input interactions"""
        code = """
        #include <iostream>
        #include <string>
        using namespace std;

        int main() {
            string name;
            int age;
            cout << "Enter your name: ";
            getline(cin, name);
            cout << "Enter your age: ";
            cin >> age;
            cout << "Hello, " << name << "! You are " << age << " years old." << endl;
            return 0;
        }
        """
        test_cases = [
            {
                'input': 'Alice Smith',
                'expected': 'Enter your age'
            },
            {
                'input': '25',
                'expected': 'Hello, Alice Smith! You are 25 years old.'
            }
        ]
        self.verify_interactive_session(code, 'cpp', test_cases)

if __name__ == '__main__':
    unittest.main(verbosity=2)