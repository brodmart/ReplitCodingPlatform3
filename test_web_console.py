import unittest
import logging
from compiler_service import compile_and_run, start_interactive_session, send_input, get_output
import time
from typing import Dict, Any

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestWebConsoleIO(unittest.TestCase):
    """Test suite for web console I/O functionality"""
    
    def verify_interactive_session(self, code: str, language: str, test_inputs: list, expected_outputs: list) -> Dict[str, Any]:
        """Helper method to verify interactive I/O sessions"""
        logger.info(f"Testing {language} interactive session")
        
        # Start interactive session
        result = start_interactive_session(code, language)
        self.assertTrue(result['success'], f"Failed to start {language} session")
        self.assertTrue(result['interactive'], "Session should be interactive")
        session_id = result['session_id']
        
        # Process each input and verify corresponding output
        for i, (test_input, expected) in enumerate(zip(test_inputs, expected_outputs)):
            time.sleep(0.5)  # Wait for I/O processing
            
            # Get current output
            output = get_output(session_id)
            self.assertTrue(output['success'], f"Failed to get output {i}")
            
            # Verify program is waiting for input
            self.assertTrue(output['waiting_for_input'], f"{language} program not waiting for input as expected")
            
            # Send input
            logger.info(f"Sending input: {test_input}")
            input_result = send_input(session_id, test_input)
            self.assertTrue(input_result['success'], f"Failed to send input: {test_input}")
            
            # Wait and get final output
            time.sleep(0.5)
            final_output = get_output(session_id)
            self.assertTrue(final_output['success'], f"Failed to get final output {i}")
            
            # Verify output contains expected text
            self.assertIn(expected, final_output['output'], 
                         f"Expected output '{expected}' not found in actual output: {final_output['output']}")
        
        return result

    def test_cpp_basic_io(self):
        """Test C++ basic input/output"""
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
        inputs = ["John Doe", "25"]
        expected = ["Hello, John Doe! You are 25 years old."]
        self.verify_interactive_session(code, 'cpp', inputs, expected)

    def test_csharp_basic_io(self):
        """Test C# basic input/output"""
        code = """
        using System;
        
        class Program {
            static void Main() {
                Console.Write("Enter your name: ");
                string name = Console.ReadLine();
                Console.Write("Enter your age: ");
                int age = Convert.ToInt32(Console.ReadLine());
                Console.WriteLine($"Hello, {name}! You are {age} years old.");
            }
        }
        """
        inputs = ["Jane Smith", "30"]
        expected = ["Hello, Jane Smith! You are 30 years old."]
        self.verify_interactive_session(code, 'csharp', inputs, expected)

    def test_cpp_complex_io(self):
        """Test C++ complex input/output scenarios"""
        code = """
        #include <iostream>
        #include <string>
        #include <vector>
        using namespace std;

        int main() {
            vector<string> items;
            string item;
            cout << "Enter items (type 'done' to finish):" << endl;
            
            while (true) {
                cout << "Item: ";
                getline(cin, item);
                if (item == "done") break;
                items.push_back(item);
            }
            
            cout << "Your items:" << endl;
            for (const auto& i : items) {
                cout << "- " << i << endl;
            }
            return 0;
        }
        """
        inputs = ["apple", "banana", "done"]
        expected = ["Your items:", "- apple", "- banana"]
        self.verify_interactive_session(code, 'cpp', inputs, expected)

    def test_csharp_complex_io(self):
        """Test C# complex input/output scenarios"""
        code = """
        using System;
        using System.Collections.Generic;
        
        class Program {
            static void Main() {
                var items = new List<string>();
                Console.WriteLine("Enter items (type 'done' to finish):");
                
                while (true) {
                    Console.Write("Item: ");
                    string item = Console.ReadLine();
                    if (item.ToLower() == "done") break;
                    items.Add(item);
                }
                
                Console.WriteLine("Your items:");
                foreach (var item in items) {
                    Console.WriteLine($"- {item}");
                }
            }
        }
        """
        inputs = ["apple", "banana", "done"]
        expected = ["Your items:", "- apple", "- banana"]
        self.verify_interactive_session(code, 'csharp', inputs, expected)

if __name__ == '__main__':
    unittest.main(verbosity=2)
