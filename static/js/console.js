/**
 * Interactive Console Implementation with Xterm.js integration
 * Enhanced version with improved error handling and terminal management
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.terminalContainer = document.getElementById(options.terminalContainer);
        if (!this.terminalContainer) {
            throw new Error('Terminal container element not found');
        }

        // Initialize terminal state
        this.initialized = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;

        // Ensure all required Xterm.js components are available
        if (!window.Terminal) {
            throw new Error('Xterm.js is not loaded');
        }
        if (!window.FitAddon) {
            throw new Error('Xterm.js FitAddon is not loaded');
        }

        this.initializeTerminal();
        this.initializeSocketIO();

        // Handle window resize
        this.resizeHandler = () => this.handleResize();
        window.addEventListener('resize', this.resizeHandler);
    }

    initializeTerminal() {
        try {
            // Initialize Xterm.js with enhanced configuration
            this.terminal = new Terminal({
                cursorBlink: true,
                fontFamily: 'Consolas, "Courier New", monospace',
                fontSize: 14,
                theme: {
                    background: '#1e1e1e',
                    foreground: '#d4d4d4',
                    cursor: '#ffffff'
                },
                allowTransparency: true,
                scrollback: 1000,
                convertEol: true,
                disableStdin: false
            });

            // Initialize addons before opening terminal
            this.fitAddon = new FitAddon.FitAddon();
            this.terminal.loadAddon(this.fitAddon);

            // Load additional addons if available
            if (window.WebLinksAddon) {
                this.terminal.loadAddon(new WebLinksAddon.WebLinksAddon());
            }
            if (window.SearchAddon) {
                this.terminal.loadAddon(new SearchAddon.SearchAddon());
            }

            // Open terminal in container
            this.terminal.open(this.terminalContainer);
            this.fitAddon.fit();

            // Basic state management
            this.currentSessionId = null;
            this.connected = false;
            this.waitingForInput = false;
            this.inputBuffer = '';
            this.inputPosition = 0;

            this.initialized = true;
            console.log('Terminal initialized successfully');

            // Set initial terminal options
            if (typeof this.terminal.options.setOption === 'function') {
                this.terminal.options.setOption('cursorBlink', true);
                this.terminal.options.setOption('cursorStyle', 'block');
            }
        } catch (error) {
            console.error('Failed to initialize terminal:', error);
            this.terminalContainer.innerHTML = `<div class="alert alert-danger">Failed to initialize terminal: ${error.message}</div>`;
            throw error;
        }
    }

    initializeSocketIO() {
        // Initialize Socket.IO with enhanced configuration
        this.socket = io({
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: this.maxReconnectAttempts,
            timeout: 20000
        });

        this.setupSocketEvents();
        this.setupTerminalEvents();
    }

    setupSocketEvents() {
        // Connection events with enhanced error handling
        this.socket.on('connect', () => {
            this.connected = true;
            this.reconnectAttempts = 0;
            this.writeLine('[System] Console connected');
            if (this.terminal.options && typeof this.terminal.options.setOption === 'function') {
                this.terminal.options.setOption('cursorBlink', true);
            }
        });

        this.socket.on('disconnect', () => {
            this.connected = false;
            this.waitingForInput = false;
            this.writeLine('[System] Console disconnected');
            if (this.terminal.options && typeof this.terminal.options.setOption === 'function') {
                this.terminal.options.setOption('cursorBlink', false);
            }
        });

        this.socket.on('connect_error', (error) => {
            console.error('Connection error:', error);
            this.writeError(`Connection error: ${error.message}`);
            this.reconnectAttempts++;

            if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                this.writeError('Maximum reconnection attempts reached. Please refresh the page.');
            }
        });

        // Enhanced output handling
        this.socket.on('output', (data) => {
            if (!data) return;

            if (data.session_id) {
                this.currentSessionId = data.session_id;
            }

            if (data.output) {
                this.write(data.output);
            }

            // Update input state with visual feedback
            this.waitingForInput = data.waiting_for_input;
            if (this.terminal.options && typeof this.terminal.options.setOption === 'function') {
                this.terminal.options.setOption('cursorStyle', this.waitingForInput ? 'block' : 'bar');
            }
        });

        // Enhanced error handling
        this.socket.on('error', (data) => {
            const errorMessage = data.message || 'An unknown error occurred';
            const errorType = data.type || 'general_error';
            this.writeError(`${errorType}: ${errorMessage}`);
            this.waitingForInput = false;
            if (this.terminal.options && typeof this.terminal.options.setOption === 'function') {
                this.terminal.options.setOption('cursorStyle', 'bar');
            }
        });
    }

    setupTerminalEvents() {
        if (!this.terminal || !this.initialized) return;

        this.terminal.onData(data => {
            if (this.waitingForInput) {
                if (data === '\r') { // Enter key
                    this.handleInput();
                } else if (data === '\u007f') { // Backspace
                    if (this.inputBuffer.length > 0 && this.inputPosition > 0) {
                        this.inputBuffer = this.inputBuffer.slice(0, this.inputPosition - 1) + 
                                         this.inputBuffer.slice(this.inputPosition);
                        this.inputPosition--;
                        // Move cursor back and rewrite the line
                        this.terminal.write('\b \b');
                    }
                } else if (data === '\u001b[D') { // Left arrow
                    if (this.inputPosition > 0) {
                        this.inputPosition--;
                        this.terminal.write(data);
                    }
                } else if (data === '\u001b[C') { // Right arrow
                    if (this.inputPosition < this.inputBuffer.length) {
                        this.inputPosition++;
                        this.terminal.write(data);
                    }
                } else if (data >= ' ' && data <= '~') { // Printable characters
                    this.inputBuffer = this.inputBuffer.slice(0, this.inputPosition) +
                                     data +
                                     this.inputBuffer.slice(this.inputPosition);
                    this.inputPosition++;
                    this.terminal.write(data);
                }
            }
        });
    }

    handleInput() {
        if (!this.waitingForInput || !this.currentSessionId || !this.initialized) return;

        const input = this.inputBuffer;
        this.inputBuffer = '';
        this.inputPosition = 0;
        this.waitingForInput = false;
        this.terminal.write('\r\n');

        this.socket.emit('input', {
            session_id: this.currentSessionId,
            input: input
        });
    }

    write(text) {
        if (!text || !this.initialized) return;
        try {
            this.terminal.write(text.replace(/\n/g, '\r\n'));
        } catch (error) {
            console.error('Error writing to terminal:', error);
        }
    }

    writeLine(text) {
        this.write(text + '\n');
    }

    writeError(message) {
        if (!this.initialized) return;
        try {
            this.terminal.write('\x1b[31m'); // Red text
            this.writeLine(`Error: ${message}`);
            this.terminal.write('\x1b[0m'); // Reset color
        } catch (error) {
            console.error('Error writing error message:', error);
            this.terminalContainer.innerHTML += `<div class="alert alert-danger">${message}</div>`;
        }
    }

    clear() {
        if (!this.initialized) return;
        try {
            this.terminal.clear();
            this.currentSessionId = null;
            this.waitingForInput = false;
            this.inputBuffer = '';
            this.inputPosition = 0;
        } catch (error) {
            console.error('Error clearing terminal:', error);
        }
    }

    handleResize() {
        if (this.initialized && this.fitAddon) {
            try {
                this.fitAddon.fit();
            } catch (error) {
                console.error('Error resizing terminal:', error);
            }
        }
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

    destroy() {
        window.removeEventListener('resize', this.resizeHandler);
        if (this.socket) {
            this.socket.disconnect();
        }
        if (this.terminal && this.initialized) {
            try {
                this.terminal.dispose();
            } catch (error) {
                console.error('Error disposing terminal:', error);
            }
        }
    }
}

// Initialize console when DOM is ready
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}