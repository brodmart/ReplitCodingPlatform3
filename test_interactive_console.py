import logging
from compiler_service import compile_and_run, send_input, get_output
import time

# Configure logging with more detailed format
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
logger = logging.getLogger(__name__)

def test_interactive_csharp():
    """Test C# interactive console functionality with enhanced error tracking"""
    print("\nTesting C# Interactive Console:")
    code = """
using System;
class Program {
    static void Main() {
        try {
            Console.Write("Enter your name: ");
            string name = Console.ReadLine();
            Console.Write("Enter your age: ");
            int age = Convert.ToInt32(Console.ReadLine());
            Console.WriteLine($"Hello {name}, you are {age} years old!");
        }
        catch (Exception e) {
            Console.WriteLine($"Error occurred: {e.Message}");
        }
    }
}
"""
    session_id = "test_interactive_" + str(hash(code))

    # Log test start
    logger.info(f"Starting test with session ID: {session_id}")
    print("Compiling and running C# code...")

    try:
        result = compile_and_run(code, "csharp", session_id=session_id)
        logger.debug(f"Initial compilation result: {result}")

        if not result['success']:
            logger.error(f"Compilation failed: {result.get('error', 'Unknown error')}")
            return result

        if result.get('interactive'):
            session_id = result['session_id']
            print("\nC# Session started successfully")
            logger.info("Session started successfully")

            # Wait for initial prompt and show it
            time.sleep(0.5)
            output = get_output(session_id)
            print("\nInitial output:", output)
            logger.debug(f"Initial output response: {output}")

            if not output['success']:
                logger.error(f"Failed to get initial output: {output.get('error')}")
                return output

            if output.get('waiting_for_input'):
                # Send first input (name) and show what we're sending
                print("\nSending input: 'John'")
                send_result = send_input(session_id, "John\n")
                print("Input result:", send_result)
                logger.debug(f"First input result: {send_result}")

                if not send_result['success']:
                    logger.error(f"Failed to send first input: {send_result.get('error')}")
                    return send_result

                time.sleep(0.5)

                # Get output after first input
                output = get_output(session_id)
                print("After name input:", output)
                logger.debug(f"Output after first input: {output}")

                if output.get('waiting_for_input'):
                    # Send second input (age) and show what we're sending
                    print("\nSending input: '25'")
                    send_result = send_input(session_id, "25\n")
                    print("Second input result:", send_result)
                    logger.debug(f"Second input result: {send_result}")

                    if not send_result['success']:
                        logger.error(f"Failed to send second input: {send_result.get('error')}")
                        return send_result

                    time.sleep(0.5)

                    # Get final output
                    final_output = get_output(session_id)
                    print("\nFinal output:", final_output)
                    logger.debug(f"Final output: {final_output}")

                    if not final_output['success']:
                        logger.error(f"Failed to get final output: {final_output.get('error')}")
                    return final_output
                else:
                    logger.error("Not waiting for age input as expected")
                    return output
            else:
                logger.error(f"Initial input state not correct: {output}")
                return output

            logger.info("Test completed successfully")
        else:
            logger.error(f"Session not interactive: {result}")
            return result

    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}", exc_info=True)
        raise

    return result

if __name__ == "__main__":
    print("\n=== Testing Interactive Console Functionality ===")
    try:
        csharp_result = test_interactive_csharp()
        print("\nC# Test Complete!")
        print("Success:", csharp_result.get('success', False))
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}", exc_info=True)
        raise