/**
 * Simplified Interactive Console Implementation
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.terminalContainer = document.getElementById(options.terminalContainer || 'consoleOutput');
        if (!this.terminalContainer) {
            throw new Error('Terminal container element not found');
        }

        // Initialize basic terminal
        this.terminal = new Terminal({
            cursorBlink: true,
            fontFamily: 'Consolas, "Courier New", monospace',
            fontSize: 14,
            theme: {
                background: '#1e1e1e',
                foreground: '#d4d4d4',
                cursor: '#ffffff'
            }
        });

        // Initialize fit addon for proper sizing
        this.fitAddon = new FitAddon.FitAddon();
        this.terminal.loadAddon(this.fitAddon);

        // Open terminal and setup events
        this.terminal.open(this.terminalContainer);
        this.fitAddon.fit();

        // Initialize Socket.IO
        this.socket = io();
        this.setupSocketEvents();

        // Basic state tracking
        this.waitingForInput = false;
        this.inputBuffer = '';

        // Handle window resize
        window.addEventListener('resize', () => this.fitAddon.fit());

        // Write initial message
        this.writeSystemMessage('Console ready');
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            this.writeSystemMessage('Connected to server');
        });

        this.socket.on('disconnect', () => {
            this.writeSystemMessage('Disconnected from server');
        });

        this.socket.on('output', (data) => {
            if (!data) return;

            if (!data.success) {
                this.writeError(data.error || 'Unknown error');
                return;
            }

            if (data.output) {
                this.write(data.output);
            }

            this.waitingForInput = !!data.waiting_for_input;
        });

        // Handle input
        this.terminal.onData(data => {
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
        });
    }

    writeSystemMessage(message) {
        this.write(`\x1b[90m[System] ${message}\x1b[0m\r\n`);
    }

    writeError(message) {
        this.write(`\x1b[31mError: ${message}\x1b[0m\r\n`);
    }

    write(text) {
        if (!text) return;
        this.terminal.write(text.replace(/\n/g, '\r\n'));
    }

    handleInput() {
        if (!this.waitingForInput) return;

        const input = this.inputBuffer;
        this.inputBuffer = '';
        this.write('\r\n');

        this.socket.emit('input', { input });
        this.waitingForInput = false;
    }

    clear() {
        this.terminal.clear();
        this.inputBuffer = '';
        this.waitingForInput = false;
    }

    compileAndRun(code) {
        this.clear();
        this.writeSystemMessage('Compiling and running code...');
        this.socket.emit('compile_and_run', { code });
    }

    destroy() {
        window.removeEventListener('resize', () => this.fitAddon.fit());
        if (this.socket) {
            this.socket.disconnect();
        }
        if (this.terminal) {
            this.terminal.dispose();
        }
    }
}

// Initialize console when DOM is ready
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}