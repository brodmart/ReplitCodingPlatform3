import time
import statistics
from compiler import compile_and_run
import logging
import os
import psutil

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_system_metrics():
    """Get current system resource usage"""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    return {
        'cpu_percent': cpu_percent,
        'memory_percent': memory.percent,
        'memory_available': memory.available / (1024 * 1024)  # MB
    }

def test_basic_compilation():
    """Test basic Hello World compilation performance"""
    code = """
using System;
class Program {
    static void Main() {
        Console.WriteLine("Hello World!");
    }
}
"""
    times = []
    system_metrics = []

    for _ in range(5):
        metrics_before = get_system_metrics()
        start = time.time()
        result = compile_and_run(code, "csharp")
        times.append(time.time() - start)
        metrics_after = get_system_metrics()

        system_metrics.append({
            'cpu_delta': metrics_after['cpu_percent'] - metrics_before['cpu_percent'],
            'memory_delta': metrics_after['memory_percent'] - metrics_before['memory_percent']
        })

        assert result['success'], f"Compilation failed: {result.get('error', 'Unknown error')}"
        assert "Hello World!" in result['output'], "Expected output not found"

    avg_time = statistics.mean(times)
    avg_cpu_delta = statistics.mean(m['cpu_delta'] for m in system_metrics)
    avg_memory_delta = statistics.mean(m['memory_delta'] for m in system_metrics)

    logger.info(f"Average compilation time: {avg_time:.2f}s")
    logger.info(f"Average CPU impact: {avg_cpu_delta:.1f}%")
    logger.info(f"Average memory impact: {avg_memory_delta:.1f}%")
    return avg_time

def test_cached_compilation():
    """Test cached compilation performance"""
    code = """
using System;
class Program {
    static void Main() {
        Console.WriteLine("Testing cache!");
    }
}
"""
    # First compilation to warm up cache
    result1 = compile_and_run(code, "csharp")
    assert result1['success'], f"Initial compilation failed: {result1.get('error', 'Unknown error')}"

    # Test cached compilation performance
    times = []
    system_metrics = []

    for _ in range(5):
        metrics_before = get_system_metrics()
        start = time.time()
        result = compile_and_run(code, "csharp")
        times.append(time.time() - start)
        metrics_after = get_system_metrics()

        system_metrics.append({
            'cpu_delta': metrics_after['cpu_percent'] - metrics_before['cpu_percent'],
            'memory_delta': metrics_after['memory_percent'] - metrics_before['memory_percent']
        })

        assert result['success'], f"Cached compilation failed: {result.get('error', 'Unknown error')}"
        assert "Testing cache!" in result['output'], "Expected output not found"
        assert result['metrics'].get('cached', False), "Result should be cached"

    avg_time = statistics.mean(times)
    avg_cpu_delta = statistics.mean(m['cpu_delta'] for m in system_metrics)
    avg_memory_delta = statistics.mean(m['memory_delta'] for m in system_metrics)

    logger.info(f"Average cached compilation time: {avg_time:.2f}s")
    logger.info(f"Average CPU impact (cached): {avg_cpu_delta:.1f}%")
    logger.info(f"Average memory impact (cached): {avg_memory_delta:.1f}%")
    return avg_time

def test_complex_compilation():
    """Test compilation with more complex code"""
    code = """
using System;
using System.Linq;
class Program {
    static void Main() {
        var numbers = Enumerable.Range(1, 100).ToArray();
        var sum = numbers.Where(x => x % 2 == 0).Sum();
        Console.WriteLine($"Sum of even numbers: {sum}");
    }
}
"""
    metrics_before = get_system_metrics()
    start = time.time()
    result = compile_and_run(code, "csharp")
    compilation_time = time.time() - start
    metrics_after = get_system_metrics()

    assert result['success'], f"Complex compilation failed: {result.get('error', 'Unknown error')}"
    assert "Sum of even numbers: 2550" in result['output'], "Expected output not found"

    cpu_impact = metrics_after['cpu_percent'] - metrics_before['cpu_percent']
    memory_impact = metrics_after['memory_percent'] - metrics_before['memory_percent']

    logger.info(f"Complex compilation time: {compilation_time:.2f}s")
    logger.info(f"CPU impact: {cpu_impact:.1f}%")
    logger.info(f"Memory impact: {memory_impact:.1f}%")
    return compilation_time

def compile_and_run_parallel(files):
    import concurrent.futures
    results = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(compile_and_run, code, "csharp") for code in files]
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({'success':False, 'error': str(e)})
    return results


def test_parallel_compilation_performance():
    """Test the performance of parallel compilation with multiple files"""
    logger.info("Starting parallel compilation performance test")

    # Create multiple test files with different content
    test_files = []
    codes = []
    for i in range(3):
        code = f"""
using System;
class Program_{i} {{
    static void Main() {{
        int sum = 0;
        for(int j = 0; j < {i+1}*1000; j++) {{
            sum += j;
        }}
        Console.WriteLine($"Sum for program {i}: {{sum}}");
    }}
}}
"""
        codes.append(code)
        filename = f'test_parallel_{i}.cs'
        with open(filename, 'w') as f:
            f.write(code)
        test_files.append(filename)

    try:
        # Test parallel compilation
        metrics_before = get_system_metrics()
        start_time = time.time()

        # Run parallel compilation
        results = compile_and_run_parallel(codes)

        end_time = time.time()
        metrics_after = get_system_metrics()

        total_time = end_time - start_time
        cpu_impact = metrics_after['cpu_percent'] - metrics_before['cpu_percent']
        memory_impact = metrics_after['memory_percent'] - metrics_before['memory_percent']

        logger.info(f"Parallel compilation completed in {total_time:.2f}s")
        logger.info(f"CPU impact: {cpu_impact:.1f}%")
        logger.info(f"Memory impact: {memory_impact:.1f}%")

        # Log individual file results
        successful_compilations = 0
        for i, result in enumerate(results):
            if result['success']:
                successful_compilations += 1
                logger.info(f"File {i+1} compiled successfully")
            else:
                logger.error(f"File {i+1} failed: {result.get('error', 'Unknown error')}")

        logger.info(f"Successfully compiled {successful_compilations} out of {len(test_files)} files")
        return total_time

    finally:
        # Cleanup test files
        for file in test_files:
            try:
                os.remove(file)
            except Exception as e:
                logger.warning(f"Failed to cleanup file {file}: {e}")

if __name__ == "__main__":
    print("\nRunning comprehensive compiler performance tests...")
    print("\n1. Testing basic compilation performance...")
    basic_time = test_basic_compilation()

    print("\n2. Testing cached compilation performance...")
    cached_time = test_cached_compilation()

    print("\n3. Testing complex compilation performance...")
    complex_time = test_complex_compilation()

    print("\n4. Testing parallel compilation performance...")
    parallel_time = test_parallel_compilation_performance()

    print("\nPerformance Summary:")
    print(f"Basic compilation: {basic_time:.2f}s")
    print(f"Cached compilation: {cached_time:.2f}s")
    print(f"Complex compilation: {complex_time:.2f}s")
    print(f"Parallel compilation: {parallel_time:.2f}s")

    # Print current system status
    current_metrics = get_system_metrics()
    print("\nSystem Status:")
    print(f"CPU Usage: {current_metrics['cpu_percent']:.1f}%")
    print(f"Memory Usage: {current_metrics['memory_percent']:.1f}%")
    print(f"Available Memory: {current_metrics['memory_available']:.0f}MB")