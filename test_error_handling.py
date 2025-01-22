import unittest
import logging
from compiler_service import compile_and_run, format_csharp_error, format_runtime_error, start_interactive_session, send_input, get_output, cleanup_session
import tempfile
import os
import time

logging.basicConfig(level=logging.DEBUG)

class TestErrorHandling(unittest.TestCase):
    def test_compilation_error(self):
        """Test C# compilation error formatting"""
        code = """
        using System;
        class Program {
            static void Main() {
                Console.WriteLine("Hello"    // Missing semicolon
                int x = "not a number";      // Type mismatch
            }
        }
        """
        result = compile_and_run(code, "csharp")
        self.assertFalse(result['success'])
        self.assertIn("Compilation Error", result['error'])
        self.assertIn("missing semicolon", result['error'].lower())

    def test_runtime_error(self):
        """Test C# runtime error formatting"""
        code = """
        using System;
        class Program {
            static void Main() {
                int[] arr = new int[3];
                Console.WriteLine(arr[5]);  // Index out of range
            }
        }
        """
        result = compile_and_run(code, "csharp")
        self.assertTrue('error' in result)
        self.assertIn("Runtime Error", result['error'])
        self.assertIn("IndexOutOfRange", result['error'])

    def test_null_reference(self):
        """Test null reference exception handling"""
        code = """
        using System;
        class Program {
            static void Main() {
                string str = null;
                Console.WriteLine(str.Length);  // Null reference
            }
        }
        """
        result = compile_and_run(code, "csharp")
        self.assertTrue('error' in result)
        self.assertIn("NullReference", result['error'])

    def test_stack_overflow(self):
        """Test stack overflow error handling"""
        code = """
        using System;
        class Program {
            static void Recurse() {
                Recurse();  // Infinite recursion
            }
            static void Main() {
                Recurse();
            }
        }
        """
        result = compile_and_run(code, "csharp")
        self.assertFalse(result['success'])
        self.assertTrue('error' in result)

class TestInteractiveConsole(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test environment"""
        for session_id in self._outcome.result.session_ids:
            cleanup_session(session_id)

    def test_interactive_csharp_compilation(self):
        """Test interactive C# console initialization and basic I/O"""
        code = """
        using System;
        class Program {
            static void Main() {
                Console.WriteLine("Enter your name:");
                string name = Console.ReadLine();
                Console.WriteLine($"Hello, {name}!");
            }
        }
        """
        # Start interactive session
        result = start_interactive_session({
            'session_id': 'test_session',
            'temp_dir': self.temp_dir
        }, code, 'csharp')

        self.assertTrue(result['success'])
        self.assertTrue(result['interactive'])
        self._outcome.result.session_ids = {result['session_id']}

        # Wait for prompt
        time.sleep(0.5)
        output = get_output(result['session_id'])
        self.assertTrue(output['success'])
        self.assertIn("Enter your name", output['output'])

        # Send input
        input_result = send_input(result['session_id'], "TestUser")
        self.assertTrue(input_result['success'])

        # Get final output
        time.sleep(0.5)
        final_output = get_output(result['session_id'])
        self.assertTrue(final_output['success'])
        self.assertIn("Hello, TestUser!", final_output['output'])

    def test_interactive_error_handling(self):
        """Test error handling in interactive mode"""
        code = """
        using System;
        class Program {
            static void Main() {
                try {
                    Console.WriteLine("Enter a number:");
                    string input = Console.ReadLine();
                    int number = int.Parse(input);
                    Console.WriteLine($"You entered: {number}");
                } catch (Exception e) {
                    Console.WriteLine($"Error: {e.Message}");
                }
            }
        }
        """
        # Start interactive session
        result = start_interactive_session({
            'session_id': 'test_error_session',
            'temp_dir': self.temp_dir
        }, code, 'csharp')

        self.assertTrue(result['success'])
        self._outcome.result.session_ids = {result['session_id']}

        # Wait for prompt
        time.sleep(0.5)
        output = get_output(result['session_id'])
        self.assertIn("Enter a number", output['output'])

        # Send invalid input
        input_result = send_input(result['session_id'], "not_a_number")
        self.assertTrue(input_result['success'])

        # Verify error handling
        time.sleep(0.5)
        error_output = get_output(result['session_id'])
        self.assertTrue(error_output['success'])
        self.assertIn("Error:", error_output['output'])

    def test_session_cleanup(self):
        """Test proper cleanup of interactive sessions"""
        code = "using System; class Program { static void Main() { Console.WriteLine(\"Test\"); } }"

        # Start session
        result = start_interactive_session({
            'session_id': 'cleanup_test',
            'temp_dir': self.temp_dir
        }, code, 'csharp')

        session_id = result['session_id']
        self._outcome.result.session_ids = {session_id}

        # Verify session exists
        self.assertTrue(result['success'])

        # Clean up session
        cleanup_session(session_id)

        # Verify session is cleaned up
        output = get_output(session_id)
        self.assertFalse(output['success'])
        self.assertIn('Invalid session', output['error'])

if __name__ == '__main__':
    unittest.main()