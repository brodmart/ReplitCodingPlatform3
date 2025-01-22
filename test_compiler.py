import logging
from compiler_service import compile_and_run

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
    result = compile_and_run(test_code, "csharp")

    print("\nCompilation Result:")
    print("Success:", result['success'])

    if not result['success']:
        print("\nErrors:")
        if 'errors' in result:
            for error in result['errors']:
                print(f"- {error['error_type']} {error['code']}: {error['message']} at line {error['line']}")

        print("\nError Summary:")
        if 'error_summary' in result:
            summary = result['error_summary']
            print(f"Total Errors: {summary['total_errors']}")
            print("\nError Patterns:")
            for pattern, count in summary['error_patterns'].items():
                print(f"- {pattern}: {count} occurrences")

    print("\nPerformance Metrics:")
    metrics = result.get('metrics', {})
    print(f"Compilation Time: {metrics.get('compilation_time', 0):.2f}s")
    print(f"Total Time: {metrics.get('total_time', 0):.2f}s")
    print(f"Peak Memory: {metrics.get('peak_memory', 0):.1f}MB")
    print(f"Average CPU Usage: {metrics.get('avg_cpu_usage', 0):.1f}%")

if __name__ == "__main__":
    test_compiler_error_tracking()