import subprocess
import tempfile
import os
import logging
import traceback
from typing import Dict, Optional, Any
from pathlib import Path
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Performance tuning constants
MAX_COMPILATION_TIME = 15  # Reduced from 20
MAX_EXECUTION_TIME = 5     # Reduced from 10
MEMORY_LIMIT = 512        # MB

def compile_and_run(code: str, language: str = 'csharp', input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Optimized compiler with minimal overhead
    """
    metrics = {'start_time': time.time()}
    logger.info(f"Starting compilation for {language}")

    if not code:
        return {
            'success': False,
            'error': "No code provided",
            'metrics': metrics
        }

    # Create temporary directory for compilation
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_file = temp_path / "Program.cs"

        # Write source code
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(code)

        try:
            # Compile directly with csc for faster compilation
            compile_start = time.time()
            compile_process = subprocess.run(
                ['csc', str(source_file), '/optimize+', '/nologo'],
                capture_output=True,
                text=True,
                timeout=MAX_COMPILATION_TIME,
                cwd=str(temp_path)
            )

            metrics['compilation_time'] = time.time() - compile_start

            if compile_process.returncode != 0:
                logger.error(f"Build failed: {compile_process.stderr}")
                return {
                    'success': False,
                    'error': format_error(compile_process.stderr),
                    'metrics': metrics
                }

            # Run the compiled program
            logger.info("Starting program execution")
            run_start = time.time()
            exe_path = temp_path / "Program.exe"

            if not exe_path.exists():
                logger.error("Compiled executable not found")
                return {
                    'success': False,
                    'error': "Build succeeded but executable not found",
                    'metrics': metrics
                }

            # Run with mono for faster execution
            run_process = subprocess.run(
                ['mono', str(exe_path)],
                input=input_data.encode() if input_data else None,
                capture_output=True,
                text=True,
                timeout=MAX_EXECUTION_TIME,
                cwd=str(temp_path)
            )

            metrics['execution_time'] = time.time() - run_start
            metrics['total_time'] = time.time() - metrics['start_time']

            if run_process.returncode != 0:
                logger.error(f"Execution failed: {run_process.stderr}")
                return {
                    'success': False,
                    'error': format_error(run_process.stderr),
                    'metrics': metrics
                }

            return {
                'success': True,
                'output': run_process.stdout,
                'metrics': metrics
            }

        except subprocess.TimeoutExpired as e:
            logger.error(f"Process timed out: {str(e)}")
            return {
                'success': False,
                'error': "Process timed out",
                'metrics': metrics
            }
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'metrics': metrics
            }

def format_error(error_msg: str) -> str:
    """Format error messages to be more user-friendly"""
    if not error_msg:
        return "Unknown error occurred"

    # Remove file paths and line numbers for cleaner output
    lines = error_msg.splitlines()
    formatted_lines = []

    for line in lines:
        if "error CS" in line:
            # Extract just the error message
            parts = line.split(': ', 1)
            if len(parts) > 1:
                formatted_lines.append(f"Compilation Error: {parts[1].strip()}")
        elif "Unhandled exception" in line:
            formatted_lines.append("Runtime Error: Program crashed during execution")

    return "\n".join(formatted_lines) if formatted_lines else error_msg.strip()

import os
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

def compile_and_run_parallel(files: List[str], language: str) -> List[Dict[str, Any]]:
    """
    Compile and run multiple files in parallel
    """
    logger.info(f"Starting parallel compilation for {len(files)} {language} files")
    start_time = time.time()

    if language != 'csharp':
        return [{'success': False, 'error': f'Language {language} not supported for parallel compilation'}]

    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
        # Read file contents
        file_contents = {}
        for file_path in files:
            logger.debug(f"Reading file: {file_path}")
            with open(file_path, 'r') as f:
                file_contents[file_path] = f.read()
        # Submit compilation tasks
        futures = []
        for file_path in files:
            logger.debug(f"Submitting compilation task for: {file_path}")
            futures.append(
                executor.submit(
                    compile_and_run,
                    code=file_contents[file_path],
                    language=language,

                )
            )

        # Collect results
        results = []
        for i, future in enumerate(futures):
            try:
                logger.debug(f"Waiting for result of file {i+1}/{len(futures)}")
                result = future.result(timeout=MAX_COMPILATION_TIME * 2)  # Double timeout for safety
                results.append(result)
                if result['success']:
                    logger.info(f"File {i+1} compiled successfully in {result['metrics']['compilation_time']:.2f}s")
                else:
                    logger.error(f"File {i+1} failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                error_msg = f'Parallel compilation failed: {str(e)}'
                logger.error(error_msg)
                results.append({
                    'success': False,
                    'error': error_msg,
                    'metrics': {'compilation_time': 0, 'execution_time': 0}
                })

        total_time = time.time() - start_time
        logger.info(f"Parallel compilation completed in {total_time:.2f}s")
        return results