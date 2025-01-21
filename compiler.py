import subprocess
import tempfile
import os
import logging
import traceback
import signal
from typing import Dict, Optional, Any
from pathlib import Path
import psutil
import time
import shutil
from threading import Lock, Thread, Event

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Performance tuning constants
MAX_COMPILATION_TIME = 20  # seconds
MAX_EXECUTION_TIME = 10    # seconds
MEMORY_LIMIT = 512        # MB
COMPILER_CACHE_DIR = "/tmp/compiler_cache"

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Compile and run code with enhanced error handling and logging
    """
    metrics = {'start_time': time.time()}
    logger.debug(f"Starting compile_and_run for {language} code, length: {len(code)} bytes")

    if not code or not language:
        return {
            'success': False,
            'error': "Code and language are required",
            'metrics': metrics
        }

    # Create a unique temporary directory for this compilation
    with tempfile.TemporaryDirectory() as temp_dir:
        project_dir = Path(temp_dir)
        source_file = project_dir / "Program.cs"
        project_file = project_dir / "program.csproj"

        # Write source code
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(code)

        # Create simple project file
        project_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
  </PropertyGroup>
</Project>"""

        with open(project_file, 'w', encoding='utf-8') as f:
            f.write(project_content)

        try:
            # Build with optimized settings
            logger.debug("Starting compilation")
            build_process = subprocess.run(
                [
                    'dotnet', 'build',
                    str(project_file),
                    '--configuration', 'Release',
                    '--nologo',
                ],
                capture_output=True,
                text=True,
                timeout=MAX_COMPILATION_TIME,
                cwd=str(project_dir)
            )

            metrics['compilation_time'] = time.time() - metrics['start_time']

            if build_process.returncode != 0:
                logger.error(f"Build failed: {build_process.stderr}")
                return {
                    'success': False,
                    'error': format_error(build_process.stderr),
                    'metrics': metrics
                }

            # Run the compiled program
            logger.debug("Starting program execution")
            run_process = subprocess.Popen(
                ['dotnet', 'run', '--project', str(project_file), '--no-build'],
                stdin=subprocess.PIPE if input_data else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(project_dir)
            )

            try:
                stdout, stderr = run_process.communicate(
                    input=input_data,
                    timeout=MAX_EXECUTION_TIME
                )

                metrics['execution_time'] = time.time() - (metrics['start_time'] + metrics['compilation_time'])
                metrics['total_time'] = time.time() - metrics['start_time']

                if run_process.returncode != 0:
                    logger.error(f"Execution failed: {stderr}")
                    return {
                        'success': False,
                        'error': format_error(stderr),
                        'metrics': metrics
                    }

                return {
                    'success': True,
                    'output': stdout,
                    'metrics': metrics
                }

            except subprocess.TimeoutExpired:
                run_process.terminate()
                run_process.wait(timeout=1)
                logger.error("Execution timed out")
                return {
                    'success': False,
                    'error': "Execution timed out",
                    'metrics': metrics
                }

        except subprocess.TimeoutExpired:
            logger.error("Compilation timed out")
            return {
                'success': False,
                'error': "Compilation timed out",
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