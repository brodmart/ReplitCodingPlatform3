import os
import subprocess
import logging
import pty
import select
import uuid
from threading import Lock
from pathlib import Path

# Enhanced logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class InteractiveSession:
    def __init__(self, session_id: str, temp_dir: str):
        self.session_id = session_id
        self.temp_dir = temp_dir
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

def get_or_create_session(session_id=None):
    """Get existing session or create new one"""
    session_id = session_id or str(uuid.uuid4())
    temp_dir = f'/tmp/compiler_{session_id}'
    os.makedirs(temp_dir, exist_ok=True)
    logger.info(f"[Session {session_id}] Created/retrieved session with temp_dir: {temp_dir}")
    return InteractiveSession(session_id, temp_dir)

def start_interactive_session(session, code: str, language: str):
    """Start an interactive C# session"""
    try:
        logger.info(f"[Session {session.session_id}] Starting interactive session")

        # Write source code
        source_file = Path(session.temp_dir) / "Program.cs"
        with open(source_file, 'w') as f:
            f.write(code)
        logger.debug(f"[Session {session.session_id}] Wrote source code to {source_file}")

        # Create project file
        project_file = Path(session.temp_dir) / "program.csproj"
        project_content = """<Project Sdk="Microsoft.NET.Sdk">
          <PropertyGroup>
            <OutputType>Exe</OutputType>
            <TargetFramework>net7.0</TargetFramework>
            <RuntimeIdentifier>linux-x64</RuntimeIdentifier>
          </PropertyGroup>
        </Project>"""

        with open(project_file, 'w') as f:
            f.write(project_content)
        logger.debug(f"[Session {session.session_id}] Created project file at {project_file}")

        # Compile
        logger.info(f"[Session {session.session_id}] Starting compilation")
        compile_result = subprocess.run(
            ['dotnet', 'build', str(project_file), '--nologo'],
            capture_output=True,
            text=True,
            cwd=session.temp_dir
        )

        if compile_result.returncode != 0:
            logger.error(f"[Session {session.session_id}] Build failed: {compile_result.stderr}")
            logger.error(f"[Session {session.session_id}] Build output: {compile_result.stdout}")
            return {'success': False, 'error': compile_result.stderr}

        logger.info(f"[Session {session.session_id}] Compilation successful")

        # Run the compiled program
        exe_path = Path(session.temp_dir) / "bin" / "Debug" / "net7.0" / "linux-x64" / "program"
        logger.info(f"[Session {session.session_id}] Starting process: {exe_path}")

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
            os.rmdir(session.temp_dir)
        logger.info(f"[Session {session_id}] Cleanup completed")
    except Exception as e:
        logger.error(f"[Session {session_id}] Error in cleanup: {e}", exc_info=True)