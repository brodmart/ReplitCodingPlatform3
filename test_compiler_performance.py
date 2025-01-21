import time
from compiler import compile_and_run
import logging

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

if __name__ == "__main__":
    test_compilation_performance()
