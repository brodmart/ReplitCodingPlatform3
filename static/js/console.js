/**
 * Optimized Interactive Console Implementation for Replit
 * Includes enhanced security, resource management and error handling
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.terminalContainer = document.getElementById(options.terminalContainer || 'consoleOutput');
        if (!this.terminalContainer) {
            throw new Error('Terminal container element not found');
        }

        // Configuration
        this.config = {
            reconnectAttempts: 3,
            reconnectDelay: 2000,
            inputRateLimit: 500, // ms between inputs
            maxOutputSize: 100 * 1024, // 100KB output limit
            bufferSize: 1024 * 8 // 8KB buffer size
        };

        // Initialize terminal with optimized settings
        this.terminal = new Terminal({
            cursorBlink: true,
            fontFamily: 'Consolas, "Courier New", monospace',
            fontSize: 14,
            theme: {
                background: '#1e1e1e',
                foreground: '#d4d4d4',
                cursor: '#ffffff'
            },
            scrollback: 1000, // Limit scrollback for memory
            cols: 80,
            rows: 24
        });

        // Initialize addons with error handling
        try {
            this.fitAddon = new FitAddon.FitAddon();
            this.terminal.loadAddon(this.fitAddon);
        } catch (error) {
            console.error('Failed to load terminal addons:', error);
            throw new Error('Terminal initialization failed');
        }

        // State management
        this.state = {
            connected: false,
            reconnecting: false,
            waitingForInput: false,
            lastInputTime: 0,
            outputSize: 0,
            inputBuffer: '',
            reconnectCount: 0
        };

        // Open terminal and setup events
        this.terminal.open(this.terminalContainer);
        this.fitAddon.fit();

        // Initialize Socket.IO with security options
        this.initializeSocket();

        // Setup event listeners
        this.setupEventListeners();

        // Write initial message
        this.writeSystemMessage('Console initializing...');
    }

    initializeSocket() {
        this.socket = io({
            path: '/socket.io/', // Explicit path
            reconnection: false, // We'll handle reconnection
            timeout: 5000,
            auth: {
                source: 'console' // Identify connection source
            }
        });

        this.setupSocketEvents();
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            this.state.connected = true;
            this.state.reconnectCount = 0;
            this.writeSystemMessage('Connected to server');
        });

        this.socket.on('disconnect', () => {
            this.state.connected = false;
            this.writeSystemMessage('Disconnected from server');
            this.handleDisconnect();
        });

        this.socket.on('connect_error', (error) => {
            console.error('Socket.IO connection error:', error);
            this.writeError(`Connection error: ${error.message}`);
        });

        this.socket.on('output', (data) => {
            if (!data) return;

            if (!data.success) {
                this.writeError(data.error || 'Unknown error');
                return;
            }

            // Check output size limits
            if (this.state.outputSize + data.output.length > this.config.maxOutputSize) {
                this.clear(true); // Clear with preserve important
            }

            if (data.output) {
                this.write(data.output);
                this.state.outputSize += data.output.length;
            }

            this.state.waitingForInput = !!data.waiting_for_input;
        });
    }

    setupEventListeners() {
        // Optimized resize handler
        const debouncedResize = this.debounce(() => this.fitAddon.fit(), 100);
        window.addEventListener('resize', debouncedResize);

        // Input handling with rate limiting
        this.terminal.onData(data => {
            const now = Date.now();
            if (now - this.state.lastInputTime < this.config.inputRateLimit) {
                return; // Rate limit exceeded
            }

            this.handleInput(data);
            this.state.lastInputTime = now;
        });
    }

    handleInput(data) {
        if (!this.state.waitingForInput || !this.state.connected) return;

        if (data === '\r') { // Enter key
            const input = this.state.inputBuffer;
            this.state.inputBuffer = '';
            this.write('\r\n');

            // Sanitize input
            const sanitizedInput = this.sanitizeInput(input);
            if (sanitizedInput) {
                this.socket.emit('input', { input: sanitizedInput });
                this.state.waitingForInput = false;
            }
        } else if (data === '\u007f') { // Backspace
            if (this.state.inputBuffer.length > 0) {
                this.state.inputBuffer = this.state.inputBuffer.slice(0, -1);
                this.terminal.write('\b \b');
            }
        } else if (data >= ' ' && data <= '~') { // Printable characters
            if (this.state.inputBuffer.length < this.config.bufferSize) {
                this.state.inputBuffer += data;
                this.terminal.write(data);
            }
        }
    }

    handleDisconnect() {
        if (this.state.reconnecting) return;

        if (this.state.reconnectCount < this.config.reconnectAttempts) {
            this.state.reconnecting = true;
            this.state.reconnectCount++;

            setTimeout(() => {
                this.writeSystemMessage(`Attempting to reconnect (${this.state.reconnectCount}/${this.config.reconnectAttempts})...`);
                this.socket.connect();
                this.state.reconnecting = false;
            }, this.config.reconnectDelay);
        } else {
            this.writeError('Connection lost. Please refresh the page.');
        }
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

    clear(preserveImportant = false) {
        this.terminal.clear();
        this.state.outputSize = 0;
        this.state.inputBuffer = '';
        if (preserveImportant && this.state.connected) {
            this.writeSystemMessage('Output cleared due to size limit');
        }
    }

    sanitizeInput(input) {
        // Basic input sanitization
        return input.slice(0, this.config.bufferSize)
                   .replace(/[^\x20-\x7E\n]/g, '');
    }

    debounce(func, wait) {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    compileAndRun(code) {
        if (!this.state.connected) {
            this.writeError('Not connected to server');
            return;
        }

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