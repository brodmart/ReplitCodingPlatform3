import unittest
import logging
import time
import uuid
import tempfile
from pathlib import Path
from compiler_service import (
    compile_and_run, start_interactive_session,
    send_input, get_output, get_or_create_session,
    cleanup_session
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
        session = get_or_create_session()
        self.active_sessions.add(session.session_id)

        result = start_interactive_session(session, code, language)
        self.assertTrue(result['success'], f"Failed to start {language} session")
        self.assertTrue(result['interactive'], "Session should be interactive")

        try:
            # Process each test case
            for i, test_case in enumerate(test_cases):
                logger.info(f"Running test case {i + 1}/{len(test_cases)}")

                # Get current output
                output = self._get_output_with_retry(session.session_id)
                self.assertTrue(output['success'], f"Failed to get output for case {i}")
                self.assertTrue(output.get('waiting_for_input', False),
                              f"{language} program not waiting for input as expected")

                # Send input
                logger.info(f"Sending input: {test_case['input']}")
                input_result = send_input(session.session_id, test_case['input'])
                self.assertTrue(input_result['success'], f"Failed to send input for case {i}")

                # Verify output
                final_output = self._get_output_with_retry(session.session_id, 
                                                         expected=test_case['expected'])
                self.assertTrue(final_output['success'], 
                              f"Failed to get final output for case {i}")
                self.assertIn(test_case['expected'], final_output['output'],
                            f"Expected '{test_case['expected']}' not found in output")

            return True
        except Exception as e:
            logger.error(f"Error in verify_interactive_session: {str(e)}")
            return False

    def _get_output_with_retry(self, session_id: str, expected: str = None, 
                             max_retries: int = 3) -> dict:
        """Get output with retries"""
        for retry in range(max_retries):
            time.sleep(0.5)
            output = get_output(session_id)
            if output['success'] and (expected is None or expected in output['output']):
                return output
            time.sleep(0.5)
        return output

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
                'input': 'John Doe\n',
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
                'input': 'Alice Smith\n',
                'expected': 'Enter your age'
            },
            {
                'input': '25\n',
                'expected': 'Hello, Alice Smith! You are 25 years old.'
            }
        ]
        self.verify_interactive_session(code, 'cpp', test_cases)

    def test_csharp_basic_io(self):
        """Test C# basic input/output interactions"""
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
                'input': 'Jane Smith\n',
                'expected': 'Hello, Jane Smith!'
            }
        ]
        self.verify_interactive_session(code, 'csharp', test_cases)

    def test_csharp_multiple_inputs(self):
        """Test C# multiple input interactions"""
        code = """
        using System;

        class Program {
            static void Main() {
                Console.Write("Enter your name: ");
                string name = Console.ReadLine();
                Console.Write("Enter your age: ");
                if (int.TryParse(Console.ReadLine(), out int age)) {
                    Console.WriteLine($"Hello, {name}! You are {age} years old.");
                } else {
                    Console.WriteLine("Invalid age entered.");
                }
            }
        }
        """
        test_cases = [
            {
                'input': 'Bob Johnson\n',
                'expected': 'Enter your age'
            },
            {
                'input': '30\n',
                'expected': 'Hello, Bob Johnson! You are 30 years old.'
            }
        ]
        self.verify_interactive_session(code, 'csharp', test_cases)

    def test_csharp_error_handling(self):
        """Test C# error handling in interactive mode"""
        code = """
        using System;

        class Program {
            static void Main() {
                try {
                    Console.Write("Enter a number: ");
                    int number = Convert.ToInt32(Console.ReadLine());
                    if (number < 0) throw new ArgumentException("Number must be positive");
                    Console.WriteLine($"You entered: {number}");
                }
                catch (Exception e) {
                    Console.WriteLine($"Error: {e.Message}");
                }
            }
        }
        """
        test_cases = [
            {
                'input': '-5\n',
                'expected': 'Error: Number must be positive'
            }
        ]
        self.verify_interactive_session(code, 'csharp', test_cases)

if __name__ == '__main__':
    unittest.main(verbosity=2)