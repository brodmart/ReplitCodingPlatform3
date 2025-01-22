import logging
from compiler_service import compile_and_run
from utils.compiler_logger import compiler_logger

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Test program with intentional errors to verify error tracking
test_code = """
using System;
namespace Test {
    class Program {
        static void Main() {
            // Intentional error - undeclared variable
            Console.WriteLine(undefinedVariable);

            // This line should not be reached
            Console.WriteLine("Hello World!");
        }
    }
}
"""

def test_compiler_error_tracking():
    """Test the enhanced compiler logging system"""
    session_id = "test_session_" + str(hash(test_code))

    # Log compilation start
    compiler_logger.log_compilation_start(session_id, test_code)

    try:
        result = compile_and_run(test_code, "csharp", session_id=session_id)

        print("\nCompilation Result:")
        print("Success:", result['success'])

        if not result['success']:
            print("\nDetailed Error Analysis:")
            error_analysis = compiler_logger.analyze_session_errors(session_id)

            print(f"\nTotal Errors: {error_analysis['error_count']}")
            print("\nError Patterns:")
            for pattern in error_analysis['patterns']:
                print(f"- {pattern['type']}: {pattern['count']} occurrences")

            print("\nError Timeline:")
            for error in error_analysis['timeline']:
                print(f"[{error['timestamp']}] {error['type']}: {error['message']}")

        print("\nPerformance Metrics:")
        metrics = result.get('metrics', {})
        print(f"Compilation Time: {metrics.get('compilation_time', 0):.2f}s")
        print(f"Total Time: {metrics.get('total_time', 0):.2f}s")
        print(f"Peak Memory: {metrics.get('peak_memory', 0):.1f}MB")
        print(f"Average CPU Usage: {metrics.get('avg_cpu_usage', 0):.1f}%")

    except Exception as e:
        compiler_logger.log_compilation_error(session_id, e, {
            'code_hash': hash(test_code),
            'error_location': 'test_compiler_error_tracking'
        })
        raise

if __name__ == "__main__":
    test_compiler_error_tracking()