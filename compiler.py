"""
Compiler service for code execution and testing.
"""
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
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Performance tuning constants
MAX_COMPILATION_TIME = 30  # Increased from 10 to 30 seconds for large files
MAX_EXECUTION_TIME = 15    # Execution timeout remains at 15 seconds
MEMORY_LIMIT = 512        # MB
COMPILER_CACHE_DIR = "/tmp/compiler_cache"

class CompilationTimeout(Exception):
    """Raised when compilation exceeds time limit"""
    pass

def compile_and_run(code: str, language: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Compile and run code with enhanced timeout handling for large files.
    """
    start_time = time.time()
    logger.debug(f"Starting compile_and_run for {language} code, length: {len(code)} bytes")

    if not code or not language:
        logger.error("Invalid input parameters")
        return {
            'success': False,
            'output': '',
            'error': "Code and language are required"
        }

    try:
        # Create compiler cache directory if it doesn't exist
        os.makedirs(COMPILER_CACHE_DIR, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="compile_", dir=COMPILER_CACHE_DIR) as temp_dir:
            if language == 'csharp':
                # Set up project structure
                project_dir = Path(temp_dir)
                source_file = project_dir / "Program.cs"
                project_file = project_dir / "program.csproj"
                bin_dir = project_dir / "bin" / "Release" / "net7.0" / "linux-x64"

                # Write source code
                logger.debug(f"Writing source code to {source_file}")
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                # Create project file with proper configuration
                project_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <RuntimeIdentifier>linux-x64</RuntimeIdentifier>
    <PublishReadyToRun>true</PublishReadyToRun>
    <SelfContained>false</SelfContained>
  </PropertyGroup>
</Project>"""

                logger.debug(f"Writing project file to {project_file}")
                with open(project_file, 'w', encoding='utf-8') as f:
                    f.write(project_content)

                # Create bin directory if it doesn't exist
                os.makedirs(bin_dir, exist_ok=True)

                # Enhanced compilation command
                compile_cmd = [
                    'dotnet',
                    'publish',
                    str(project_file),
                    '--configuration', 'Release',
                    '--runtime', 'linux-x64',
                    '--self-contained', 'false',
                    '--output', str(bin_dir),
                    '-nologo',
                    '/p:GenerateFullPaths=true',
                    '/consoleloggerparameters:NoSummary'
                ]

                logger.debug(f"Starting C# compilation with command: {' '.join(compile_cmd)}")
                compile_start = time.time()

                try:
                    # Set up enhanced compilation environment
                    env = os.environ.copy()
                    env.update({
                        'DOTNET_CLI_HOME': str(project_dir),
                        'DOTNET_NOLOGO': '1',
                        'DOTNET_CLI_TELEMETRY_OPTOUT': '1'
                    })

                    # First restore packages
                    logger.debug("Restoring NuGet packages...")
                    restore_cmd = ['dotnet', 'restore', str(project_file)]
                    restore_process = subprocess.run(
                        restore_cmd,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd=str(project_dir),
                        env=env
                    )

                    if restore_process.returncode != 0:
                        logger.error(f"Package restore failed: {restore_process.stderr}")
                        return {
                            'success': False,
                            'error': f"Package restore failed: {restore_process.stderr}",
                            'metrics': {'compilation_time': time.time() - compile_start}
                        }

                    compile_process = subprocess.run(
                        compile_cmd,
                        capture_output=True,
                        text=True,
                        timeout=MAX_COMPILATION_TIME,
                        cwd=str(project_dir),
                        env=env
                    )

                    compile_time = time.time() - compile_start
                    logger.debug(f"Compilation completed in {compile_time:.2f}s")

                    if compile_process.returncode != 0:
                        error_msg = format_csharp_error(compile_process.stderr)
                        logger.error(f"Compilation failed: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg,
                            'metrics': {
                                'compilation_time': compile_time
                            }
                        }

                    # Verify the executable exists
                    dll_path = bin_dir / "program.dll"
                    executable = bin_dir / "program"

                    if dll_path.exists():
                        logger.debug(f"Found program.dll at {dll_path}")
                        run_cmd = ['dotnet', str(dll_path)]
                    elif executable.exists():
                        logger.debug(f"Found executable at {executable}")
                        os.chmod(executable, 0o755)
                        run_cmd = [str(executable)]
                    else:
                        error_msg = f"Compilation succeeded but no executable found in {bin_dir}"
                        logger.error(error_msg)
                        logger.debug(f"Directory contents: {list(bin_dir.glob('*'))}")
                        return {
                            'success': False,
                            'error': error_msg,
                            'metrics': {
                                'compilation_time': compile_time
                            }
                        }

                    logger.debug(f"Running program with command: {' '.join(run_cmd)}")
                    run_start = time.time()

                    run_process = subprocess.run(
                        run_cmd,
                        input=input_data.encode() if input_data else None,
                        capture_output=True,
                        text=True,
                        timeout=MAX_EXECUTION_TIME,
                        cwd=str(project_dir),
                        env=env
                    )

                    run_time = time.time() - run_start
                    total_time = time.time() - start_time

                    logger.debug(f"Execution completed in {run_time:.2f}s")

                    if run_process.returncode != 0:
                        error_msg = format_runtime_error(run_process.stderr)
                        logger.error(f"Execution failed: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg,
                            'metrics': {
                                'compilation_time': compile_time,
                                'execution_time': run_time,
                                'total_time': total_time
                            }
                        }

                    return {
                        'success': True,
                        'output': run_process.stdout,
                        'metrics': {
                            'compilation_time': compile_time,
                            'execution_time': run_time,
                            'total_time': total_time
                        }
                    }

                except subprocess.TimeoutExpired as e:
                    elapsed_time = time.time() - start_time
                    phase = "compilation" if elapsed_time < MAX_COMPILATION_TIME else "execution"
                    error_msg = f"{phase.capitalize()} timed out after {elapsed_time:.2f} seconds"
                    logger.error(error_msg)
                    return {
                        'success': False,
                        'error': error_msg,
                        'metrics': {
                            'time_elapsed': elapsed_time
                        }
                    }

            else:
                error_msg = f"Unsupported language: {language}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg
                }

    except Exception as e:
        error_msg = f"Unexpected error occurred: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }

def format_csharp_error(error_msg: str) -> str:
    """Format C# compilation errors to be more user-friendly"""
    try:
        if "error CS" in error_msg:
            # Extract the error code and message
            match = re.search(r'error CS\d+:(.+?)(?:\r|\n|$)', error_msg)
            if match:
                return f"Compilation Error: {match.group(1).strip()}"
        return f"Compilation Error: {error_msg.strip()}"
    except Exception as e:
        logger.error(f"Error formatting C# error message: {str(e)}")
        return f"Compilation Error: {error_msg}"

def format_runtime_error(error_msg: str) -> str:
    """Format runtime errors to be more user-friendly"""
    try:
        common_errors = {
            "System.NullReferenceException": "Attempted to use a null object",
            "System.IndexOutOfRangeException": "Array index out of bounds",
            "System.DivideByZeroException": "Division by zero detected",
            "System.InvalidOperationException": "Invalid operation",
            "System.ArgumentException": "Invalid argument provided",
            "System.FormatException": "Invalid format"
        }

        for error_type, message in common_errors.items():
            if error_type in error_msg:
                return f"Runtime Error: {message}"
        return f"Runtime Error: {error_msg}"
    except Exception:
        return f"Runtime Error: {error_msg}"