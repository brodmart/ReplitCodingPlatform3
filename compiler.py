import subprocess
import tempfile
import os
import logging
import traceback
from typing import Dict, Optional, Any, List
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Performance tuning constants
MAX_COMPILATION_TIME = 15  # seconds
MAX_EXECUTION_TIME = 5    # seconds
MEMORY_LIMIT = 512       # MB
MAX_PARALLEL_COMPILATIONS = os.cpu_count() or 4
CACHE_DIR = "/tmp/compiler_cache"

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_key(code: str) -> str:
    """Generate a unique cache key for the code"""
    return hashlib.sha256(code.encode()).hexdigest()

def compile_and_run(code: str, language: str = 'csharp', input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Optimized compiler with minimal overhead and improved caching
    """
    metrics = {'start_time': time.time()}
    logger.debug(f"Starting compilation for code length: {len(code)}")

    if not code:
        return {
            'success': False,
            'error': "No code provided",
            'metrics': metrics
        }

    # Check cache first
    cache_key = get_cache_key(code)
    cache_path = Path(CACHE_DIR) / cache_key

    if cache_path.exists():
        logger.debug("Using cached compilation")
        metrics['cached'] = True
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                # Copy cached files
                os.system(f'cp -r {cache_path}/* {temp_path}/')

                # Run the cached program
                run_process = subprocess.run(
                    ['dotnet', f'{temp_path}/program.dll'],
                    input=input_data.encode() if input_data else None,
                    capture_output=True,
                    text=True,
                    timeout=MAX_EXECUTION_TIME,
                    cwd=str(temp_path)
                )

                metrics['compilation_time'] = 0  # Cached, no compilation needed
                metrics['execution_time'] = time.time() - metrics['start_time']
                metrics['total_time'] = metrics['execution_time']

                if run_process.returncode != 0:
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
        except Exception as e:
            logger.warning(f"Cache use failed, falling back to full compilation: {e}")

    # Create temporary directory for compilation
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_file = temp_path / "Program.cs"

        try:
            # Write source code
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(code)

            # Create optimized project file
            project_file = temp_path / "program.csproj"
            project_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <PublishReadyToRun>true</PublishReadyToRun>
    <Configuration>Release</Configuration>
  </PropertyGroup>
</Project>"""

            with open(project_file, 'w', encoding='utf-8') as f:
                f.write(project_content)

            # Build with optimized settings
            logger.debug("Starting build process")
            build_process = subprocess.run(
                ['dotnet', 'build', str(project_file),
                 '--configuration', 'Release',
                 '--nologo',
                 '/p:GenerateFullPaths=true',
                 '/consoleloggerparameters:NoSummary'],
                capture_output=True,
                text=True,
                timeout=MAX_COMPILATION_TIME,
                cwd=str(temp_path)
            )

            metrics['compilation_time'] = time.time() - metrics['start_time']

            if build_process.returncode != 0:
                logger.error(f"Build failed: {build_process.stderr}")
                return {
                    'success': False,
                    'error': format_error(build_process.stderr),
                    'metrics': metrics
                }

            # Cache successful compilation
            os.makedirs(cache_path, exist_ok=True)
            os.system(f'cp -r {temp_path}/bin/Release/net7.0/* {cache_path}/')

            # Run the program
            logger.debug("Starting program execution")
            run_process = subprocess.run(
                ['dotnet', 'run', '--project', str(project_file),
                 '--no-build',
                 '--configuration', 'Release'],
                input=input_data.encode() if input_data else None,
                capture_output=True,
                text=True,
                timeout=MAX_EXECUTION_TIME,
                cwd=str(temp_path)
            )

            metrics['execution_time'] = time.time() - (metrics['start_time'] + metrics['compilation_time'])
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

        except subprocess.TimeoutExpired:
            logger.error("Process timed out")
            return {
                'success': False,
                'error': "Process timed out",
                'metrics': metrics
            }
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'metrics': metrics
            }

def format_error(error_msg: str) -> str:
    """Format error messages to be more user-friendly"""
    if not error_msg:
        return "Unknown error occurred"

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

def compile_and_run_parallel(files: List[str], language: str = 'csharp') -> List[Dict[str, Any]]:
    """
    Optimized parallel compilation with improved resource management
    """
    logger.info(f"Starting parallel compilation for {len(files)} {language} files")
    start_time = time.time()

    if language != 'csharp':
        return [{'success': False, 'error': f'Language {language} not supported for parallel compilation'}]

    # Read all files first to prevent I/O bottlenecks during compilation
    file_contents = {}
    for file_path in files:
        try:
            with open(file_path, 'r') as f:
                file_contents[file_path] = f.read()
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return [{'success': False, 'error': f'Failed to read {file_path}: {str(e)}'}]

    results = [None] * len(files)

    def compile_file(idx: int, code: str) -> Dict[str, Any]:
        return idx, compile_and_run(code, language)

    # Use ThreadPoolExecutor with a fixed number of workers
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_COMPILATIONS) as executor:
        future_to_idx = {
            executor.submit(compile_file, idx, content): idx
            for idx, content in enumerate(file_contents.values())
        }

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                file_idx, result = future.result(timeout=MAX_COMPILATION_TIME * 2)
                results[file_idx] = result
                if result['success']:
                    logger.info(f"File {idx+1} compiled successfully in {result['metrics']['compilation_time']:.2f}s")
                else:
                    logger.error(f"File {idx+1} failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                error_msg = f'Parallel compilation failed: {str(e)}'
                logger.error(error_msg)
                results[idx] = {
                    'success': False,
                    'error': error_msg,
                    'metrics': {'compilation_time': 0, 'execution_time': 0}
                }

    total_time = time.time() - start_time
    logger.info(f"Parallel compilation completed in {total_time:.2f}s")
    return results

def run_parallel_compilation(files: List[str], cwd: str, env: Dict[str, str], timeout: int = 30) -> List[subprocess.CompletedProcess]:
    """Execute parallel compilation of multiple files"""
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_COMPILATIONS) as executor:
        futures = []
        for file in files:
            project_file = Path(file).parent / "program.csproj"
            if not project_file.exists():
                # Create project file if it doesn't exist
                project_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <PublishReadyToRun>true</PublishReadyToRun>
    <Configuration>Release</Configuration>
  </PropertyGroup>
</Project>"""
                with open(project_file, 'w', encoding='utf-8') as f:
                    f.write(project_content)

            # Submit build task
            futures.append(
                executor.submit(
                    subprocess.run,
                    ['dotnet', 'build', str(project_file),
                     '--configuration', 'Release',
                     '--nologo',
                     '/p:GenerateFullPaths=true',
                     '/consoleloggerparameters:NoSummary'],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd,
                    env=env
                )
            )

        # Wait for all compilations to complete
        results = []
        for future in as_completed(futures):
            try:
                result = future.result(timeout=timeout)
                results.append(result)
            except Exception as e:
                logger.error(f"Parallel compilation failed: {e}")
                # Create a failed result
                results.append(
                    subprocess.CompletedProcess(
                        args=[],
                        returncode=1,
                        stdout="",
                        stderr=str(e)
                    )
                )

        return results