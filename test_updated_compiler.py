from compiler_service import (
    compile_and_run, start_interactive_session, 
    send_input, get_output, CompilerSession
)
import tempfile
import uuid
import time

def test_interactive_cpp():
    print("Testing C++ interactive program...")
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

    # Start interactive session
    session_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp(prefix='test_cpp_')
    session = CompilerSession(session_id, temp_dir)

    result = start_interactive_session(session, code, 'cpp')
    print("Session result:", result)

    if result['success']:
        # Wait for initial output and prompt
        time.sleep(0.5)  # Give process time to start and produce output
        output = get_output(session_id)
        print("Initial output:", output)

        # Send input only if waiting for input
        if output['waiting_for_input']:
            input_result = send_input(session_id, "John")
            print("Input result:", input_result)

            # Wait for processing
            time.sleep(0.5)
            final_output = get_output(session_id)
            print("Final output:", final_output)
        else:
            print("Process not waiting for input as expected")

def test_interactive_csharp():
    print("\nTesting C# interactive program...")
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

    # Start interactive session
    session_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp(prefix='test_csharp_')
    session = CompilerSession(session_id, temp_dir)

    result = start_interactive_session(session, code, 'csharp')
    print("Session result:", result)

    if result['success']:
        # Wait for initial output and prompt
        time.sleep(0.5)  # Give process time to start and produce output
        output = get_output(session_id)
        print("Initial output:", output)

        # Send input only if waiting for input
        if output['waiting_for_input']:
            input_result = send_input(session_id, "Jane")
            print("Input result:", input_result)

            # Wait for processing
            time.sleep(0.5)
            final_output = get_output(session_id)
            print("Final output:", final_output)
        else:
            print("Process not waiting for input as expected")

if __name__ == "__main__":
    test_interactive_cpp()
    test_interactive_csharp()