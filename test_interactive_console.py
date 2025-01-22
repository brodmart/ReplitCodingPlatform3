import logging
from compiler_service import compile_and_run, send_input, get_output
from utils.compiler_logger import compiler_logger
import time

# Only enable logging when running tests directly
if __name__ == "__main__":
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
    session_id = "test_interactive_" + str(hash(code))

    # Log test start
    compiler_logger.log_compilation_start(session_id, code)
    print("Compiling and running C# code...")

    try:
        result = compile_and_run(code, "csharp", session_id=session_id)

        if result['success'] and result.get('interactive'):
            session_id = result['session_id']
            print("\nC# Session started successfully")
            compiler_logger.log_execution_state(session_id, 'session_started')

            # Wait for initial prompt and show it
            time.sleep(1)
            output = get_output(session_id)
            if not output['success']:
                compiler_logger.log_runtime_error(session_id, "Failed to get initial output", output)
            print("\nInitial prompt:", output.get('output', ''))

            # Send first input (name) and show what we're sending
            print("\nSending input: 'John'")
            send_result = send_input(session_id, "John")
            if not send_result['success']:
                compiler_logger.log_runtime_error(session_id, "Failed to send input", send_result)
            time.sleep(0.5)

            # Get output after first input
            output = get_output(session_id)
            if not output['success']:
                compiler_logger.log_runtime_error(session_id, "Failed to get output after first input", output)
            print("Program output:", output.get('output', ''))

            # Send second input (age) and show what we're sending
            print("\nSending input: '25'")
            send_result = send_input(session_id, "25")
            if not send_result['success']:
                compiler_logger.log_runtime_error(session_id, "Failed to send second input", send_result)
            time.sleep(0.5)

            # Get final output
            final_output = get_output(session_id)
            if not final_output['success']:
                compiler_logger.log_runtime_error(session_id, "Failed to get final output", final_output)
            print("\nFinal program output:", final_output.get('output', ''))
            result['test_output'] = final_output

            compiler_logger.log_execution_state(session_id, 'test_completed', {
                'outputs_received': bool(final_output.get('output')),
                'test_success': True
            })
        else:
            compiler_logger.log_compilation_error(session_id, Exception(result.get('error', 'Unknown error')), {
                'compilation_result': result
            })

    except Exception as e:
        compiler_logger.log_runtime_error(session_id, str(e), {
            'stage': 'test_execution',
            'code_hash': hash(code)
        })
        raise

    return result

if __name__ == "__main__":
    # Only run tests when explicitly called
    print("\n=== Testing Interactive Console Functionality ===")
    print("\nTesting C# Interactive Console:")
    try:
        csharp_result = test_csharp_interactive()
        print("\nC# Test Complete!")
        print("C# Success:", csharp_result['success'])
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise