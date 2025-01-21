from compiler import compile_and_run

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
    
    # First run - should compile regularly
    result1 = compile_and_run(test_code, 'csharp')
    print("First run metrics:", result1['metrics'])
    
    # Second run - should use cache
    result2 = compile_and_run(test_code, 'csharp')
    print("Second run metrics:", result2['metrics'])

    # Verify caching worked
    assert result2['metrics']['cached'] == True, "Second run should use cache"
    print("Caching test passed!")

if __name__ == '__main__':
    test_warmup()
