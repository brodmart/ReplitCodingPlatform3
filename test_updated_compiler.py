from compiler_service import compile_and_run

test_code = '''
using System;
class Program {
    static void Main() {
        Console.WriteLine("Testing updated compiler service");
    }
}
'''

result = compile_and_run(test_code, 'csharp')
print(result)
