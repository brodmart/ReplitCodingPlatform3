import time
from compiler import compile_and_run, run_parallel_compilation
import logging
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_compilation_performance():
    logger.info("Starting compilation performance test")

    # Read the large test file
    with open('test_large.cs', 'r') as f:
        code = f.read()

    # Run multiple compilation tests
    num_tests = 3
    compilation_times = []

    for i in range(num_tests):
        logger.info(f"Running test {i+1}/{num_tests}")
        start_time = time.time()
        result = compile_and_run(code, 'csharp')
        end_time = time.time()

        if result['success']:
            metrics = result.get('metrics', {})
            compilation_time = metrics.get('compilation_time', 0)
            execution_time = metrics.get('execution_time', 0)
            total_time = end_time - start_time

            logger.info(f"Test {i+1} results:")
            logger.info(f"Compilation time: {compilation_time:.2f}s")
            logger.info(f"Execution time: {execution_time:.2f}s")
            logger.info(f"Total time: {total_time:.2f}s")

            compilation_times.append(compilation_time)
        else:
            logger.error(f"Test {i+1} failed: {result.get('error')}")

    if compilation_times:
        avg_time = sum(compilation_times) / len(compilation_times)
        logger.info(f"\nAverage compilation time: {avg_time:.2f}s")
        logger.info(f"Best time: {min(compilation_times):.2f}s")
        logger.info(f"Worst time: {max(compilation_times):.2f}s")

def compile_and_run_parallel(files, language='csharp'):
    """Run compilation in parallel for multiple files"""
    try:
        # Create temporary directory for compilation
        os.makedirs('temp', exist_ok=True)
        cwd = os.path.abspath('temp')

        # Setup environment
        env = os.environ.copy()
        env['DOTNET_CLI_HOME'] = cwd
        env['DOTNET_NOLOGO'] = '1'
        env['DOTNET_CLI_TELEMETRY_OPTOUT'] = '1'

        # Run parallel compilation
        results = run_parallel_compilation(files, cwd, env, timeout=30)
        return [{'success': r.returncode == 0, 'output': r.stdout, 'error': r.stderr} for r in results]
    except Exception as e:
        logger.error(f"Parallel compilation failed: {e}")
        return [{'success': False, 'error': str(e)}] * len(files)

def test_parallel_compilation_performance():
    """Test the performance of parallel compilation with multiple files"""
    logger.info("Starting parallel compilation performance test")

    # Create multiple test files with different content
    test_files = []
    for i in range(3):
        filename = f'test_parallel_{i}.cs'
        with open(filename, 'w') as f:
            f.write(f"""
using System;

namespace TestProgram_{i}
{{
    class Program
    {{
        static void Main()
        {{
            Console.WriteLine("Test program {i}");
            for(int j = 0; j < {i+1}*1000; j++)
            {{
                Math.Pow(j, 2);
            }}
        }}
    }}
}}
""")
        test_files.append(filename)

    try:
        # Test parallel compilation
        start_time = time.time()
        results = compile_and_run_parallel(test_files)
        end_time = time.time()

        total_time = end_time - start_time
        logger.info(f"Parallel compilation completed in {total_time:.2f}s")

        # Log individual file results
        for i, result in enumerate(results):
            if result['success']:
                logger.info(f"File {i+1} compilation successful")
            else:
                logger.error(f"File {i+1} failed: {result.get('error')}")

    finally:
        # Cleanup test files
        for file in test_files:
            try:
                os.remove(file)
            except Exception as e:
                logger.warning(f"Failed to cleanup file {file}: {e}")

        # Cleanup temp directory
        try:
            import shutil
            shutil.rmtree('temp', ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {e}")

if __name__ == "__main__":
    test_compilation_performance()  # Run original test
    test_parallel_compilation_performance()  # Run parallel test