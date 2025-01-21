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
                executable = project_dir / "bin/Debug/net7.0/program"

                # Create project file
                project_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
</Project>"""

                logger.debug(f"Writing project file to {project_file}")
                with open(project_file, 'w', encoding='utf-8') as f:
                    f.write(project_content)

                logger.debug(f"Writing source code to {source_file}")
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(code)

                # Enhanced compilation command with optimization flags
                compile_cmd = [
                    'dotnet',
                    'build',
                    str(project_file),
                    '-o',
                    str(executable.parent),
                    '/p:GenerateFullPaths=true',
                    '/consoleloggerparameters:NoSummary'
                ]

                logger.debug("Starting C# compilation with enhanced settings")
                compile_start = time.time()

                try:
                    logger.debug(f"Executing compilation command: {' '.join(compile_cmd)}")
                    compile_process = subprocess.run(
                        compile_cmd,
                        capture_output=True,
                        text=True,
                        timeout=MAX_COMPILATION_TIME,
                        cwd=str(project_dir)
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

                    logger.debug("Compilation successful, preparing execution")
                    os.chmod(executable, 0o755)

                    # Execute with optimized Mono runtime settings
                    run_cmd = ['dotnet', str(executable)]
                    run_start = time.time()

                    run_process = subprocess.run(
                        run_cmd,
                        capture_output=True,
                        text=True,
                        timeout=MAX_EXECUTION_TIME,
                        cwd=str(project_dir)
                    )

                    run_time = time.time() - run_start
                    total_time = time.time() - start_time

                    logger.debug(f"Execution completed in {run_time:.2f}s")
                    logger.debug(f"Total processing time: {total_time:.2f}s")

                    return {
                        'success': run_process.returncode == 0,
                        'output': run_process.stdout,
                        'error': run_process.stderr if run_process.returncode != 0 else None,
                        'metrics': {
                            'compilation_time': compile_time,
                            'execution_time': run_time,
                            'total_time': total_time
                        }
                    }

                except subprocess.TimeoutExpired as e:
                    elapsed_time = time.time() - start_time
                    phase = "compilation" if elapsed_time < MAX_COMPILATION_TIME else "execution"
                    logger.error(f"{phase.capitalize()} timed out after {elapsed_time:.2f}s")
                    return {
                        'success': False,
                        'error': f"{phase.capitalize()} timed out after {elapsed_time:.2f} seconds",
                        'metrics': {
                            'time_elapsed': elapsed_time
                        }
                    }

            else:
                logger.error(f"Unsupported language: {language}")
                return {
                    'success': False,
                    'error': f"Unsupported language: {language}"
                }

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Unexpected error: {str(e)}\n{error_details}")
        return {
            'success': False,
            'error': f"An error occurred while processing your code: {str(e)}"
        }