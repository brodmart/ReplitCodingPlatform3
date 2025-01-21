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

        with tempfile.TemporaryDirectory() as temp_dir:
            if language == 'csharp':
                # Set up project structure
                project_dir = Path(temp_dir)
                source_file = project_dir / "Program.cs"
                project_file = project_dir / "program.csproj"
                bin_dir = project_dir / "bin" / "Debug" / "net7.0"
                executable = bin_dir / "program"

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

                logger.debug(f"Writing source code to {source_file}")
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                # Create bin directory if it doesn't exist
                os.makedirs(bin_dir, exist_ok=True)

                # Enhanced compilation command
                compile_cmd = [
                    'dotnet',
                    'build',
                    str(project_file),
                    '--output',
                    str(bin_dir),
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
                        'DOTNET_CLI_TELEMETRY_OPTOUT': '1',
                        'DOTNET_ROLL_FORWARD': 'Major'
                    })

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
                        logger.error(f"Compilation failed: {compile_process.stderr}")
                        return {
                            'success': False,
                            'error': compile_process.stderr,
                            'metrics': {
                                'compilation_time': compile_time
                            }
                        }

                    # Verify the executable exists
                    if not executable.exists():
                        error_msg = f"Compilation succeeded but executable not found at {executable}"
                        logger.error(error_msg)
                        return {
                            'success': False,
                            'error': error_msg,
                            'metrics': {
                                'compilation_time': compile_time
                            }
                        }

                    logger.debug("Compilation successful, preparing execution")
                    run_cmd = ['dotnet', str(executable)]
                    run_start = time.time()

                    run_process = subprocess.run(
                        run_cmd,
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
                        logger.error(f"Execution failed: {run_process.stderr}")
                        return {
                            'success': False,
                            'error': run_process.stderr,
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