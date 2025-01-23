/**
 * Interactive Console Implementation with Xterm.js integration
 * Enhanced version with improved I/O synchronization
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.terminalContainer = document.getElementById(options.terminalContainer || 'consoleOutput');
        if (!this.terminalContainer) {
            throw new Error('Terminal container element not found');
        }

        // Initialize terminal state
        this.initialized = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;

        // Enhanced I/O state management
        this.outputQueue = [];
        this.isProcessingOutput = false;
        this.lastOutputTime = 0;
        this.outputDelay = 50; // ms between outputs
        this.pendingInput = false;

        // Ensure all required Xterm.js components are available
        if (!window.Terminal) {
            throw new Error('Xterm.js is not loaded');
        }
        if (!window.FitAddon) {
            throw new Error('Xterm.js FitAddon is not loaded');
        }

        // C# Console state
        this.consoleColors = {
            Black: '\x1b[30m',
            DarkRed: '\x1b[31m',
            DarkGreen: '\x1b[32m',
            DarkYellow: '\x1b[33m',
            DarkBlue: '\x1b[34m',
            DarkMagenta: '\x1b[35m',
            DarkCyan: '\x1b[36m',
            Gray: '\x1b[37m',
            DarkGray: '\x1b[90m',
            Red: '\x1b[91m',
            Green: '\x1b[92m',
            Yellow: '\x1b[93m',
            Blue: '\x1b[94m',
            Magenta: '\x1b[95m',
            Cyan: '\x1b[96m',
            White: '\x1b[97m'
        };
        this.currentForegroundColor = this.consoleColors.Gray;
        this.currentBackgroundColor = '\x1b[40m';
        this.cursorPosition = { x: 0, y: 0 };

        // Initialize components
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
                disableStdin: false,
                cursorStyle: 'block'
            });

            // Initialize addons
            this.fitAddon = new FitAddon.FitAddon();
            this.terminal.loadAddon(this.fitAddon);

            if (window.WebLinksAddon) {
                this.terminal.loadAddon(new WebLinksAddon.WebLinksAddon());
            }
            if (window.SearchAddon) {
                this.terminal.loadAddon(new SearchAddon.SearchAddon());
            }

            // Open terminal in container
            this.terminal.open(this.terminalContainer);
            this.fitAddon.fit();

            // Enhanced state management
            this.currentSessionId = null;
            this.connected = false;
            this.waitingForInput = false;
            this.inputBuffer = '';
            this.inputPosition = 0;
            this.inputHistory = [];
            this.historyPosition = -1;

            this.initialized = true;
            console.log('Terminal initialized successfully');
        } catch (error) {
            console.error('Failed to initialize terminal:', error);
            throw error;
        }
    }

    initializeSocketIO() {
        this.socket = io({
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: this.maxReconnectAttempts,
            timeout: 20000,
            transports: ['websocket', 'polling']
        });

        this.setupSocketEvents();
        this.setupTerminalEvents();
    }

    setupSocketEvents() {
        // Enhanced connection handling
        this.socket.on('connect', () => {
            this.connected = true;
            this.reconnectAttempts = 0;
            this.writeSystemMessage('Console connected');
            this.terminal.focus();
        });

        this.socket.on('disconnect', () => {
            this.connected = false;
            this.waitingForInput = false;
            this.writeSystemMessage('Console disconnected');
        });

        // Enhanced output handling with queuing
        this.socket.on('output', async (data) => {
            if (!data) return;

            if (data.session_id) {
                this.currentSessionId = data.session_id;
            }

            // Process output first
            if (data.output) {
                await this.queueOutput(data.output);
            }

            // Wait for output processing before updating input state
            await this.waitForOutputProcessing();

            // Update input state after ensuring output is processed
            this.waitingForInput = !!data.waiting_for_input;
            if (this.waitingForInput && !this.pendingInput) {
                this.terminal.focus();
                this.inputBuffer = '';
                this.inputPosition = 0;
            }
        });

        // Enhanced error handling
        this.socket.on('error', async (data) => {
            const errorMessage = data.message || 'An unknown error occurred';
            const errorType = data.type || 'general_error';
            await this.writeError(`${errorType}: ${errorMessage}`);
            this.waitingForInput = false;
            this.pendingInput = false;
        });
        // Console operations with improved synchronization
        this.socket.on('console_operation', async (data) => {
            if (!data || !data.operation) return;

            // Wait for any pending output before processing operation
            await this.waitForOutputProcessing();

            switch (data.operation) {
                case 'Write':
                case 'WriteLine':
                    await this.handleWrite(data);
                    break;
                case 'Clear':
                    this.clear();
                    break;
                case 'SetCursorPosition':
                    this.setCursorPosition(data.x, data.y);
                    break;
                case 'SetForegroundColor':
                    this.setForegroundColor(data.color);
                    break;
                case 'SetBackgroundColor':
                    this.setBackgroundColor(data.color);
                    break;
                case 'ResetColor':
                    this.resetColors();
                    break;
            }
        });
        // Handle compilation success
        this.socket.on('compilation_success', (data) => {
            if (data && data.session_id) {
                this.currentSessionId = data.session_id;
            }
        });
    }

    async queueOutput(text) {
        this.outputQueue.push(text);
        if (!this.isProcessingOutput) {
            await this.processOutputQueue();
        }
    }

    async processOutputQueue() {
        if (this.isProcessingOutput || this.outputQueue.length === 0) return;

        this.isProcessingOutput = true;
        try {
            while (this.outputQueue.length > 0) {
                const now = Date.now();
                const timeSinceLastOutput = now - this.lastOutputTime;

                if (timeSinceLastOutput < this.outputDelay) {
                    await new Promise(resolve => setTimeout(resolve, this.outputDelay - timeSinceLastOutput));
                }

                const output = this.outputQueue.shift();
                await this.write(output);
                this.lastOutputTime = Date.now();
            }
        } finally {
            this.isProcessingOutput = false;
        }
    }

    async waitForOutputProcessing() {
        while (this.isProcessingOutput || this.outputQueue.length > 0) {
            await new Promise(resolve => setTimeout(resolve, 10));
        }
    }

    setupTerminalEvents() {
        if (!this.terminal || !this.initialized) return;

        this.terminal.onData(data => {
            if (this.waitingForInput && !this.pendingInput) {
                if (data === '\r') { // Enter key
                    this.handleInput();
                } else if (data === '\u007f') { // Backspace
                    if (this.inputBuffer.length > 0 && this.inputPosition > 0) {
                        this.inputBuffer = this.inputBuffer.slice(0, this.inputPosition - 1) + 
                                        this.inputBuffer.slice(this.inputPosition);
                        this.inputPosition--;
                        this.terminal.write('\b \b');
                    }
                } else if (data === '\u001b[A') { // Up arrow
                    this.navigateHistory('up');
                } else if (data === '\u001b[B') { // Down arrow
                    this.navigateHistory('down');
                } else if (data >= ' ' && data <= '~') { // Printable characters
                    this.inputBuffer = this.inputBuffer.slice(0, this.inputPosition) +
                                    data +
                                    this.inputBuffer.slice(this.inputPosition);
                    this.inputPosition++;
                    this.terminal.write(data);
                }
            }
        });

        this.terminal.element.addEventListener('click', () => {
            if (this.waitingForInput && !this.pendingInput) {
                this.terminal.focus();
            }
        });
    }

    async handleInput() {
        if (!this.waitingForInput || !this.currentSessionId || this.pendingInput) return;

        const input = this.inputBuffer;
        this.pendingInput = true;

        try {
            // Add to history if not empty and different from last entry
            if (input && (this.inputHistory.length === 0 || this.inputHistory[0] !== input)) {
                this.inputHistory.unshift(input);
                if (this.inputHistory.length > 50) {
                    this.inputHistory.pop();
                }
            }

            // Clear input state
            this.inputBuffer = '';
            this.inputPosition = 0;
            this.historyPosition = -1;

            // Write newline
            await this.write('\r\n');

            // Emit input event
            this.socket.emit('input', {
                session_id: this.currentSessionId,
                input: input
            });

            // Reset state after sending input
            this.waitingForInput = false;
            await new Promise(resolve => setTimeout(resolve, 50));

        } catch (error) {
            console.error('Error handling input:', error);
            await this.writeError('Failed to send input');
        } finally {
            this.pendingInput = false;
        }
    }

    async writeSystemMessage(message) {
        await this.write('\x1b[90m[System] ' + message + '\x1b[0m\r\n');
    }

    async write(text) {
        if (!text || !this.initialized) return;
        try {
            this.terminal.write(text.replace(/\n/g, '\r\n'));
        } catch (error) {
            console.error('Error writing to terminal:', error);
        }
    }

    async writeError(message) {
        if (!this.initialized) return;
        try {
            await this.write('\x1b[31m'); // Red text
            await this.write('Error: ' + message + '\r\n');
            await this.write('\x1b[0m'); // Reset color
        } catch (error) {
            console.error('Error writing error message:', error);
        }
    }

    clear() {
        if (!this.initialized) return;
        try {
            this.terminal.clear();
            this.outputQueue = [];
            this.isProcessingOutput = false;
            this.currentSessionId = null;
            this.waitingForInput = false;
            this.inputBuffer = '';
            this.inputPosition = 0;
            this.pendingInput = false;
            this.resetColors();
        } catch (error) {
            console.error('Error clearing terminal:', error);
        }
    }

    handleWrite(data) {
        const text = data.text || '';
        const isLine = data.operation === 'WriteLine';

        // Apply current colors
        this.write(this.currentForegroundColor + this.currentBackgroundColor);
        this.write(text + (isLine ? '\r\n' : ''));

        // Reset colors after write if needed
        if (data.resetColors) {
            this.resetColors();
        }
    }

    setForegroundColor(color) {
        if (this.consoleColors[color]) {
            this.currentForegroundColor = this.consoleColors[color];
            this.write(this.currentForegroundColor);
        }
    }

    setBackgroundColor(color) {
        const bgColor = color.replace('Dark', '') + 'm';
        this.currentBackgroundColor = '\x1b[4' + (color.startsWith('Dark') ? '0' : '1') + bgColor;
        this.write(this.currentBackgroundColor);
    }

    resetColors() {
        this.currentForegroundColor = this.consoleColors.Gray;
        this.currentBackgroundColor = '\x1b[40m';
        this.write('\x1b[0m'); // Reset all attributes
    }

    setCursorPosition(x, y) {
        if (!this.initialized) return;
        try {
            // Save current position
            this.cursorPosition.x = x;
            this.cursorPosition.y = y;

            // ANSI escape sequence for cursor position
            this.terminal.write(`\x1b[${y + 1};${x + 1}H`);
        } catch (error) {
            console.error('Error setting cursor position:', error);
        }
    }

    navigateHistory(direction) {
        if (direction === 'up' && this.historyPosition < this.inputHistory.length - 1) {
            this.historyPosition++;
        } else if (direction === 'down' && this.historyPosition >= 0) {
            this.historyPosition--;
        } else {
            return;
        }

        // Clear current input
        while (this.inputPosition > 0) {
            this.terminal.write('\b \b');
            this.inputPosition--;
        }

        if (this.historyPosition >= 0 && this.historyPosition < this.inputHistory.length) {
            this.inputBuffer = this.inputHistory[this.historyPosition];
        } else {
            this.inputBuffer = '';
        }

        this.inputPosition = this.inputBuffer.length;
        this.terminal.write(this.inputBuffer);
    }


    compileAndRun(code) {
        if (!this.connected) {
            this.writeError('Not connected to server');
            return;
        }

        this.clear();
        this.writeSystemMessage('Compiling and running code...');

        // Reset state before new compilation
        this.waitingForInput = false;
        this.inputBuffer = '';
        this.inputPosition = 0;
        this.pendingInput = false;

        this.socket.emit('compile_and_run', { code });
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