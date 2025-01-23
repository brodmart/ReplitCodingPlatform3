/**
 * Interactive Console Implementation with Xterm.js integration
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

        // Handle terminal resize
        window.addEventListener('resize', () => {
            this.fitAddon.fit();
        });

        this.currentSessionId = null;
        this.connected = false;
        this.waitingForInput = false;
        this.inputBuffer = '';
        this.inputCallback = null;

        // Initialize Socket.IO
        this.socket = io({
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: 5
        });

        this.setupSocketEvents();
        this.setupTerminalEvents();

        // Log initialization
        console.log('Console initialized with terminal');
    }

    setupSocketEvents() {
        // Connection events
        this.socket.on('connect', () => {
            console.log('Socket connected');
            this.connected = true;
            this.writeLine('Console connected');
        });

        this.socket.on('disconnect', () => {
            console.log('Socket disconnected');
            this.connected = false;
            this.writeLine('Console disconnected. Attempting to reconnect...');
            this.waitingForInput = false;
        });

        this.socket.on('connect_error', (error) => {
            console.error('Connection error:', error);
            this.writeError(`Connection error: ${error.message}`);
            this.waitingForInput = false;
        });

        // Compilation events
        this.socket.on('compilation_success', (data) => {
            console.log('Compilation success:', data);
            if (data && data.session_id) {
                this.currentSessionId = data.session_id;
            }
            this.writeLine('Program started successfully...');
        });

        this.socket.on('compilation_error', (data) => {
            console.error('Compilation error:', data);
            this.writeError(data.error || 'Compilation failed');
            this.currentSessionId = null;
            this.waitingForInput = false;
        });

        // Output events
        this.socket.on('output', (data) => {
            console.log('Received output:', data);
            if (!data) return;

            if (data.session_id) {
                this.currentSessionId = data.session_id;
            }

            if (data.output) {
                this.write(data.output);
            }

            this.waitingForInput = data.waiting_for_input;
            if (data.waiting_for_input) {
                console.log('Waiting for user input');
                this.startInput();
            }
        });

        // Error events
        this.socket.on('error', (data) => {
            console.error('Received error:', data);
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

    startInput() {
        this.waitingForInput = true;
        this.inputBuffer = '';
    }

    handleInput() {
        if (!this.waitingForInput) return;

        const input = this.inputBuffer;
        this.inputBuffer = '';
        this.waitingForInput = false;
        this.terminal.write('\r\n');

        if (!this.currentSessionId) {
            this.writeError('No active session');
            return;
        }

        console.log('Sending input:', input);
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

        console.log('Compiling code:', code);
        this.clear();
        this.writeLine('Compiling and running code...');
        this.socket.emit('compile_and_run', { code });
    }
}

// Initialize console when DOM is ready
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}