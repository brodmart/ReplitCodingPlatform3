import logging
from compiler_service import compile_and_run, send_input, get_output
import time

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_csharp_interactive():
    """Test C# interactive console functionality"""
    print("\nStarting C# Interactive Test:")
    code = """
using System;
class Program {
    static void Main() {
        Console.Write("Enter your name: ");
        string name = Console.ReadLine();
        Console.Write("Enter your age: ");
        int age = Convert.ToInt32(Console.ReadLine());
        Console.WriteLine($"Hello {name}, you are {age} years old!");
    }
}
"""
    print("Compiling and running C# code...")
    result = compile_and_run(code, "csharp")

    if result['success'] and result.get('interactive'):
        session_id = result['session_id']
        print("\nC# Session started successfully")

        # Wait for initial prompt and show it
        time.sleep(1)
        output = get_output(session_id)
        print("\nInitial prompt:", output.get('output', ''))

        # Send first input (name) and show what we're sending
        print("\nSending input: 'John'")
        send_input(session_id, "John")
        time.sleep(0.5)

        # Get output after first input
        output = get_output(session_id)
        print("Program output:", output.get('output', ''))

        # Send second input (age) and show what we're sending
        print("\nSending input: '25'")
        send_input(session_id, "25")
        time.sleep(0.5)

        # Get final output
        final_output = get_output(session_id)
        print("\nFinal program output:", final_output.get('output', ''))
        result['test_output'] = final_output

    return result

def test_cpp_interactive():
    """Test C++ interactive console functionality"""
    print("\nStarting C++ Interactive Test:")
    code = """
#include <iostream>
#include <string>
using namespace std;

int main() {
    string name;
    int age;
    cout << "Enter your name: ";
    cin >> name;
    cout << "Enter your age: ";
    cin >> age;
    cout << "Hello " << name << ", you are " << age << " years old!" << endl;
    return 0;
}
"""
    print("Compiling and running C++ code...")
    result = compile_and_run(code, "cpp")

    if result['success'] and result.get('interactive'):
        session_id = result['session_id']
        print("\nC++ Session started successfully")

        # Wait for initial prompt and show it
        time.sleep(1)
        output = get_output(session_id)
        print("\nInitial prompt:", output.get('output', ''))

        # Send first input (name) and show what we're sending
        print("\nSending input: 'Jane'")
        send_input(session_id, "Jane")
        time.sleep(0.5)

        # Get output after first input
        output = get_output(session_id)
        print("Program output:", output.get('output', ''))

        # Send second input (age) and show what we're sending
        print("\nSending input: '30'")
        send_input(session_id, "30")
        time.sleep(0.5)

        # Get final output
        final_output = get_output(session_id)
        print("\nFinal program output:", final_output.get('output', ''))
        result['test_output'] = final_output

    return result

if __name__ == "__main__":
    print("\n=== Testing Interactive Console Functionality ===")
    print("\nTesting C# Interactive Console:")
    csharp_result = test_csharp_interactive()
    print("\nC# Test Complete!")
    print("C# Success:", csharp_result['success'])

    print("\nTesting C++ Interactive Console:")
    cpp_result = test_cpp_interactive()
    print("\nC++ Test Complete!")
    print("C++ Success:", cpp_result['success'])