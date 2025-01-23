/**
 * Interactive Console Implementation with Xterm.js integration
 * Simplified version with core functionality
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.terminalContainer = document.getElementById(options.terminalContainer);
        if (!this.terminalContainer) {
            throw new Error('Terminal container element not found');
        }

        // Initialize Xterm.js
        this.terminal = new Terminal({
            cursorBlink: true,
            fontFamily: 'Consolas, "Courier New", monospace',
            fontSize: 14,
            theme: {
                background: '#1e1e1e',
                foreground: '#d4d4d4'
            }
        });

        // Initialize the FitAddon for terminal resizing
        this.fitAddon = new FitAddon.FitAddon();
        this.terminal.loadAddon(this.fitAddon);

        // Open terminal in container
        this.terminal.open(this.terminalContainer);
        this.fitAddon.fit();

        // Basic state management
        this.currentSessionId = null;
        this.connected = false;
        this.waitingForInput = false;
        this.inputBuffer = '';

        // Initialize Socket.IO with basic configuration
        this.socket = io({
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionAttempts: 3
        });

        this.setupSocketEvents();
        this.setupTerminalEvents();

        // Handle window resize
        window.addEventListener('resize', () => this.fitAddon.fit());
    }

    setupSocketEvents() {
        // Connection events
        this.socket.on('connect', () => {
            this.connected = true;
            this.writeLine('Console connected');
        });

        this.socket.on('disconnect', () => {
            this.connected = false;
            this.writeLine('Console disconnected');
            this.waitingForInput = false;
        });

        // Simplified output handling
        this.socket.on('output', (data) => {
            if (!data) return;

            if (data.session_id) {
                this.currentSessionId = data.session_id;
            }

            if (data.output) {
                this.write(data.output);
            }

            // Update input state
            this.waitingForInput = data.waiting_for_input;
        });

        // Error handling
        this.socket.on('error', (data) => {
            this.writeError(data.message || 'An error occurred');
            this.waitingForInput = false;
        });
    }

    setupTerminalEvents() {
        this.terminal.onData(data => {
            if (this.waitingForInput) {
                if (data === '\r') { // Enter key
                    this.handleInput();
                } else if (data === '\u007f') { // Backspace
                    if (this.inputBuffer.length > 0) {
                        this.inputBuffer = this.inputBuffer.slice(0, -1);
                        this.terminal.write('\b \b');
                    }
                } else if (data >= ' ' && data <= '~') { // Printable characters
                    this.inputBuffer += data;
                    this.terminal.write(data);
                }
            }
        });
    }

    handleInput() {
        if (!this.waitingForInput || !this.currentSessionId) return;

        const input = this.inputBuffer;
        this.inputBuffer = '';
        this.waitingForInput = false;
        this.terminal.write('\r\n');

        this.socket.emit('input', {
            session_id: this.currentSessionId,
            input: input
        });
    }

    write(text) {
        if (!text) return;
        this.terminal.write(text.replace(/\n/g, '\r\n'));
    }

    writeLine(text) {
        this.write(text + '\n');
    }

    writeError(message) {
        this.terminal.write('\x1b[31m'); // Red text
        this.writeLine(`Error: ${message}`);
        this.terminal.write('\x1b[0m'); // Reset color
    }

    clear() {
        this.terminal.clear();
        this.currentSessionId = null;
        this.waitingForInput = false;
        this.inputBuffer = '';
    }

    compileAndRun(code) {
        if (!this.connected) {
            this.writeError('Not connected to server');
            return;
        }

        this.clear();
        this.writeLine('Compiling and running code...');
        this.socket.emit('compile_and_run', { code });
    }
}

// Initialize console when DOM is ready
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}