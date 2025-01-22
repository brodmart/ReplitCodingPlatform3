import subprocess
import tempfile
import os
import logging
from typing import Dict, Optional, Any
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def compile_and_run(code: str, input_data: Optional[str] = None) -> Dict[str, Any]:
    """
    Simple C# compiler and execution service focused on basic programs.
    """
    logger.debug(f"Starting compilation for code length: {len(code)}")

    if not code:
        return {
            'success': False,
            'error': "No code provided"
        }

    # Create temporary directory for compilation
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_file = temp_path / "Program.cs"

        # Write source code
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(code)

        try:
            # Create optimized project file
            project_file = temp_path / "program.csproj"
            project_content = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net7.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <PublishReadyToRun>true</PublishReadyToRun>
  </PropertyGroup>
</Project>"""

            with open(project_file, 'w', encoding='utf-8') as f:
                f.write(project_content)

            # Build the project with optimized settings
            logger.debug("Starting build process")
            build_process = subprocess.run(
                ['dotnet', 'build', str(project_file), '--nologo', '--configuration', 'Release'],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(temp_path)
            )

            if build_process.returncode != 0:
                logger.error(f"Build failed: {build_process.stderr}")
                return {
                    'success': False,
                    'error': format_error(build_process.stderr)
                }

            # Run the compiled program
            logger.debug("Starting program execution")
            run_process = subprocess.run(
                ['dotnet', 'run', '--project', str(project_file), '--no-build'],
                input=input_data.encode() if input_data else None,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(temp_path)
            )

            if run_process.returncode != 0:
                logger.error(f"Execution failed: {run_process.stderr}")
                return {
                    'success': False,
                    'error': format_error(run_process.stderr)
                }

            return {
                'success': True,
                'output': run_process.stdout
            }

        except subprocess.TimeoutExpired as e:
            logger.error(f"Process timed out: {str(e)}")
            return {
                'success': False,
                'error': "Process timed out"
            }
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
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