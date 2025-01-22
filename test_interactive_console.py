import logging
from compiler_service import compile_and_run, send_input, get_output
from utils.compiler_logger import compiler_logger
import time

# Only enable logging when running tests directly
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_interactive_csharp():
    """Test C# interactive console functionality"""
    print("\nTesting C# Interactive Console:")
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
        print("Initial result:", result)
        final_output = None  # Initialize final_output

        if result['success'] and result.get('interactive'):
            session_id = result['session_id']
            print("\nC# Session started successfully")
            compiler_logger.log_execution_state(session_id, 'session_started')

            # Wait for initial prompt and show it
            time.sleep(1)
            output = get_output(session_id)
            print("\nInitial output:", output)

            if output['success'] and output.get('waiting_for_input'):
                # Send first input (name) and show what we're sending
                print("\nSending input: 'John'")
                send_result = send_input(session_id, "John\n")
                print("Input result:", send_result)
                time.sleep(0.5)

                # Get output after first input
                output = get_output(session_id)
                print("After name input:", output)

                if output['success'] and output.get('waiting_for_input'):
                    # Send second input (age) and show what we're sending
                    print("\nSending input: '25'")
                    send_result = send_input(session_id, "25\n")
                    print("Second input result:", send_result)
                    time.sleep(0.5)

                    # Get final output
                    final_output = get_output(session_id)
                    print("\nFinal output:", final_output)
                else:
                    print("Not waiting for age input as expected")
            else:
                print("Initial input state not correct:", output)

            if final_output:  # Only log completion if we have final output
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
    print("\n=== Testing Interactive Console Functionality ===")
    try:
        csharp_result = test_interactive_csharp()
        print("\nC# Test Complete!")
        print("Success:", csharp_result['success'])
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        raise