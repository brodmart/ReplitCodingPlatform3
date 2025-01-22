import unittest
import logging
import time
from compiler_service import compile_and_run, send_input, get_output
from utils.compiler_logger import compiler_logger

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestWebConsoleIO(unittest.TestCase):
    """Test suite for web console I/O functionality"""

    def test_cpp_basic_io(self):
        """Test C++ basic input/output"""
        print("\nTesting C++ Basic I/O:")
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
        session_id = "test_interactive_" + str(hash(code))

        try:
            # Start compilation and run
            compiler_logger.log_compilation_start(session_id, code)
            result = compile_and_run(code, 'cpp', session_id=session_id)

            if result['success'] and result.get('interactive'):
                # Wait for initial prompt
                time.sleep(1)
                output = get_output(session_id)
                if not output['success']:
                    compiler_logger.log_runtime_error(session_id, "Failed to get initial output", output)
                    self.fail("Failed to get initial output")
                print(f"\nInitial prompt: {output.get('output', '')}")

                # Send input
                test_input = "John Doe"
                print(f"\nSending input: '{test_input}'")
                send_result = send_input(session_id, test_input)
                if not send_result['success']:
                    compiler_logger.log_runtime_error(session_id, "Failed to send input", send_result)
                    self.fail("Failed to send input")

                # Wait for processing
                time.sleep(0.5)

                # Get final output
                final_output = get_output(session_id)
                if not final_output['success']:
                    compiler_logger.log_runtime_error(session_id, "Failed to get final output", final_output)
                    self.fail("Failed to get final output")
                print(f"\nFinal output: {final_output.get('output', '')}")

                # Verify expected output
                expected = "Hello, John Doe!"
                self.assertIn(expected, final_output['output'], 
                            f"Expected output '{expected}' not found in actual output")

                compiler_logger.log_execution_state(session_id, 'test_completed', {
                    'outputs_received': True,
                    'test_success': True
                })
            else:
                compiler_logger.log_compilation_error(
                    session_id,
                    Exception(result.get('error', 'Unknown error')),
                    {'compilation_result': result}
                )
                self.fail(f"Failed to start interactive session: {result.get('error', 'Unknown error')}")

        except Exception as e:
            compiler_logger.log_runtime_error(session_id, str(e))
            logger.error(f"Test failed with error: {str(e)}")
            raise

    def test_csharp_basic_io(self):
        """Test C# basic input/output"""
        print("\nTesting C# Basic I/O:")
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
        session_id = "test_interactive_" + str(hash(code))

        try:
            # Start compilation and run
            compiler_logger.log_compilation_start(session_id, code)
            result = compile_and_run(code, 'csharp', session_id=session_id)

            if result['success'] and result.get('interactive'):
                # Wait for initial prompt
                time.sleep(1)
                output = get_output(session_id)
                if not output['success']:
                    compiler_logger.log_runtime_error(session_id, "Failed to get initial output", output)
                    self.fail("Failed to get initial output")
                print(f"\nInitial prompt: {output.get('output', '')}")

                # Send input
                test_input = "Jane Smith"
                print(f"\nSending input: '{test_input}'")
                send_result = send_input(session_id, test_input)
                if not send_result['success']:
                    compiler_logger.log_runtime_error(session_id, "Failed to send input", send_result)
                    self.fail("Failed to send input")

                # Wait for processing
                time.sleep(0.5)

                # Get final output
                final_output = get_output(session_id)
                if not final_output['success']:
                    compiler_logger.log_runtime_error(session_id, "Failed to get final output", final_output)
                    self.fail("Failed to get final output")
                print(f"\nFinal output: {final_output.get('output', '')}")

                # Verify expected output
                expected = "Hello, Jane Smith!"
                self.assertIn(expected, final_output['output'],
                            f"Expected output '{expected}' not found in actual output")

                compiler_logger.log_execution_state(session_id, 'test_completed', {
                    'outputs_received': True,
                    'test_success': True
                })
            else:
                compiler_logger.log_compilation_error(
                    session_id,
                    Exception(result.get('error', 'Unknown error')),
                    {'compilation_result': result}
                )
                self.fail(f"Failed to start interactive session: {result.get('error', 'Unknown error')}")

        except Exception as e:
            compiler_logger.log_runtime_error(session_id, str(e))
            logger.error(f"Test failed with error: {str(e)}")
            raise

if __name__ == '__main__':
    unittest.main(verbosity=2)