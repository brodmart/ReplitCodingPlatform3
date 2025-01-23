import os
import subprocess
import logging
import pty
import select
import uuid
from threading import Lock
from pathlib import Path
import shutil

# Enhanced logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Use project directory instead of /tmp
COMPILER_DIR = os.path.join(os.getcwd(), 'compiler_workspace')
os.makedirs(COMPILER_DIR, exist_ok=True)

class InteractiveSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.temp_dir = os.path.join(COMPILER_DIR, session_id)
        self.master_fd = None
        self.slave_fd = None
        self.process = None
        self.output_buffer = []
        self.waiting_for_input = False

        # Initialize PTY
        try:
            self.master_fd, self.slave_fd = pty.openpty()
            logger.info(f"[Session {session_id}] PTY initialized - master_fd: {self.master_fd}, slave_fd: {self.slave_fd}")
        except Exception as e:
            logger.error(f"[Session {session_id}] Failed to initialize PTY: {e}")

def cleanup_old_sessions():
    """Clean up old compilation directories"""
    try:
        if os.path.exists(COMPILER_DIR):
            for item in os.listdir(COMPILER_DIR):
                item_path = os.path.join(COMPILER_DIR, item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception as e:
                    logger.error(f"Error cleaning up {item_path}: {e}")
    except Exception as e:
        logger.error(f"Error in cleanup_old_sessions: {e}")

def get_or_create_session(session_id=None):
    """Get existing session or create new one"""
    cleanup_old_sessions()  # Clean up before creating new session

    session_id = session_id or str(uuid.uuid4())
    session_dir = os.path.join(COMPILER_DIR, session_id)

    # Remove existing session directory if it exists
    if os.path.exists(session_dir):
        try:
            shutil.rmtree(session_dir)
        except Exception as e:
            logger.error(f"Error cleaning up existing session directory: {e}")

    os.makedirs(session_dir, exist_ok=True)
    logger.info(f"[Session {session_id}] Created/retrieved session in {session_dir}")
    return InteractiveSession(session_id)

def start_interactive_session(session, code: str, language: str):
    """Start an interactive C# session"""
    try:
        logger.info(f"[Session {session.session_id}] Starting interactive session")
        logger.info(f"[Session {session.session_id}] Received code:")
        logger.info("-" * 40)
        logger.info(code)
        logger.info("-" * 40)

        # Write source code
        source_file = Path(session.temp_dir) / "Program.cs"
        with open(source_file, 'w') as f:
            f.write(code)
        logger.debug(f"[Session {session.session_id}] Wrote code to {source_file}")

        # Create minimal project file
        project_file = Path(session.temp_dir) / "program.csproj"
        project_content = """<Project Sdk="Microsoft.NET.Sdk">
          <PropertyGroup>
            <OutputType>Exe</OutputType>
            <TargetFramework>net7.0</TargetFramework>
            <RuntimeIdentifier>linux-x64</RuntimeIdentifier>
            <PublishSingleFile>true</PublishSingleFile>
            <SelfContained>false</SelfContained>
            <EnableDefaultItems>false</EnableDefaultItems>
            <GenerateAssemblyInfo>false</GenerateAssemblyInfo>
          </PropertyGroup>
          <ItemGroup>
            <Compile Include="Program.cs" />
          </ItemGroup>
        </Project>"""

        with open(project_file, 'w') as f:
            f.write(project_content)
        logger.debug(f"[Session {session.session_id}] Created project file at {project_file}")

        # Compile with optimized settings
        logger.info(f"[Session {session.session_id}] Starting compilation")
        compile_result = subprocess.run(
            ['dotnet', 'build', str(project_file), '--nologo', '-c', 'Release',
             '/p:GenerateFullPaths=true',
             '/consoleloggerparameters:NoSummary'],
            capture_output=True,
            text=True,
            cwd=session.temp_dir
        )

        if compile_result.returncode != 0:
            logger.error(f"[Session {session.session_id}] Build failed:")
            logger.error(f"STDOUT:\n{compile_result.stdout}")
            logger.error(f"STDERR:\n{compile_result.stderr}")
            return {'success': False, 'error': compile_result.stderr}

        logger.info(f"[Session {session.session_id}] Compilation successful")

        # Run the compiled program
        exe_path = Path(session.temp_dir) / "bin" / "Release" / "net7.0" / "linux-x64" / "program"
        logger.info(f"[Session {session.session_id}] Starting process: {exe_path}")

        # Verify executable exists
        if not os.path.exists(exe_path):
            logger.error(f"[Session {session.session_id}] Executable not found at {exe_path}")
            return {'success': False, 'error': 'Compiled executable not found'}

        session.process = subprocess.Popen(
            [str(exe_path)],
            stdin=session.slave_fd,
            stdout=session.slave_fd,
            stderr=session.slave_fd,
            close_fds=True
        )

        logger.info(f"[Session {session.session_id}] Process started with PID: {session.process.pid}")

        return {
            'success': True,
            'session_id': session.session_id
        }

    except Exception as e:
        logger.error(f"[Session {session.session_id}] Error in start_interactive_session: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def get_output(session_id: str):
    """Get output from the session"""
    try:
        session = get_or_create_session(session_id)
        if not session.master_fd:
            logger.error(f"[Session {session_id}] Invalid session - no master_fd")
            return {'success': False, 'error': 'Invalid session'}

        ready, _, _ = select.select([session.master_fd], [], [], 0.1)
        if ready:
            try:
                output = os.read(session.master_fd, 1024).decode()
                logger.debug(f"[Session {session_id}] Received output: {output!r}")
                session.waiting_for_input = 'input' in output.lower() or '?' in output
                logger.debug(f"[Session {session_id}] Waiting for input: {session.waiting_for_input}")
                return {
                    'success': True,
                    'output': output,
                    'waiting_for_input': session.waiting_for_input
                }
            except OSError as e:
                logger.error(f"[Session {session_id}] Error reading from PTY: {e}")
                return {'success': False, 'error': f'Error reading output: {e}'}

        logger.debug(f"[Session {session_id}] No output available")
        return {
            'success': True,
            'output': '',
            'waiting_for_input': session.waiting_for_input
        }
    except Exception as e:
        logger.error(f"[Session {session_id}] Error in get_output: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def send_input(session_id: str, input_text: str):
    """Send input to the session"""
    try:
        logger.info(f"[Session {session_id}] Attempting to send input: {input_text!r}")
        session = get_or_create_session(session_id)
        if not session.master_fd:
            logger.error(f"[Session {session_id}] Invalid session - no master_fd")
            return {'success': False, 'error': 'Invalid session'}

        if not input_text.endswith('\n'):
            input_text += '\n'

        try:
            bytes_written = os.write(session.master_fd, input_text.encode())
            logger.info(f"[Session {session_id}] Successfully wrote {bytes_written} bytes")
            return {'success': True}
        except OSError as e:
            logger.error(f"[Session {session_id}] Error writing to PTY: {e}")
            return {'success': False, 'error': f'Error sending input: {e}'}

    except Exception as e:
        logger.error(f"[Session {session_id}] Error in send_input: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def cleanup_session(session_id: str):
    """Clean up session resources"""
    try:
        logger.info(f"[Session {session_id}] Starting cleanup")
        session = get_or_create_session(session_id)
        if session.process:
            logger.info(f"[Session {session_id}] Terminating process")
            session.process.terminate()
        if session.master_fd:
            logger.info(f"[Session {session_id}] Closing master_fd")
            os.close(session.master_fd)
        if session.slave_fd:
            logger.info(f"[Session {session_id}] Closing slave_fd")
            os.close(session.slave_fd)
        if os.path.exists(session.temp_dir):
            logger.info(f"[Session {session_id}] Removing temp directory")
            shutil.rmtree(session.temp_dir)
        logger.info(f"[Session {session_id}] Cleanup completed")
    except Exception as e:
        logger.error(f"[Session {session_id}] Error in cleanup: {e}", exc_info=True)