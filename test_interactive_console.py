import logging
from compiler_service import compile_and_run, send_input, get_output
import time

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_csharp_interactive():
    """Test C# interactive console functionality"""
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
    logger.info("Testing C# interactive console")
    result = compile_and_run(code, "csharp")

    if result['success'] and result.get('interactive'):
        session_id = result['session_id']

        # Wait for initial prompt
        time.sleep(1)
        output = get_output(session_id)
        logger.info(f"Initial output: {output}")

        if output['success']:
            # Send test inputs
            send_input(session_id, "John")
            time.sleep(0.5)
            send_input(session_id, "25")
            time.sleep(0.5)

            # Get final output
            final_output = get_output(session_id)
            logger.info(f"Final output: {final_output}")
            result['test_output'] = final_output

    return result

def test_cpp_interactive():
    """Test C++ interactive console functionality"""
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
    logger.info("Testing C++ interactive console")
    result = compile_and_run(code, "cpp")

    if result['success'] and result.get('interactive'):
        session_id = result['session_id']

        # Wait for initial prompt
        time.sleep(1)
        output = get_output(session_id)
        logger.info(f"Initial output: {output}")

        if output['success']:
            # Send test inputs
            send_input(session_id, "Jane")
            time.sleep(0.5)
            send_input(session_id, "30")
            time.sleep(0.5)

            # Get final output
            final_output = get_output(session_id)
            logger.info(f"Final output: {final_output}")
            result['test_output'] = final_output

    return result

if __name__ == "__main__":
    print("\nTesting C# Interactive Console:")
    csharp_result = test_csharp_interactive()
    print("C# Result:", csharp_result)

    print("\nTesting C++ Interactive Console:")
    cpp_result = test_cpp_interactive()
    print("C++ Result:", cpp_result)