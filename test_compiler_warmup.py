"""
Compiler warmup testing module.
Only loads when explicitly running warmup tests.
"""
import threading
import time
from compiler import compile_and_run

def warmup_compiler():
    """Pre-warm the compiler with a simple compilation"""
    # Only import logging when running tests
    if __name__ == "__main__":
        import logging
        logging.basicConfig(level=logging.INFO)

    warmup_code = """
using System;
class Program {
    static void Main() {
        Console.WriteLine("Warmup complete");
    }
}
"""
    result = compile_and_run(warmup_code, "csharp")
    return result['success']

def start_warmup():
    """Start compiler warmup in a background thread"""
    thread = threading.Thread(target=warmup_compiler)
    thread.daemon = True
    thread.start()
    return thread

def test_warmup():
    # Simple test code
    test_code = '''
using System;
class Program {
    static void Main() {
        Console.WriteLine("Hello World!");
    }
}
'''

    # Start compiler warmup
    print("Starting compiler warmup...")
    warmup_thread = start_warmup()

    # First run - should compile regularly
    result1 = compile_and_run(test_code, 'csharp')
    print("First run metrics:", result1['metrics'])

    # Wait for warmup to complete
    warmup_thread.join()
    print("Warmup complete!")

    # Second run - should use cache
    result2 = compile_and_run(test_code, 'csharp')
    print("Second run metrics:", result2['metrics'])

    # Verify caching worked
    assert result2['metrics']['cached'] == True, "Second run should use cache"
    print("Caching test passed!")

if __name__ == "__main__":
    test_warmup()