/**
 * Interactive Console for handling program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.outputElement = options.outputElement || document.getElementById('console-output');
        this.inputElement = options.inputElement || document.getElementById('console-input');
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;
        this.currentLanguage = 'csharp';
        this.compilationTimeout = 30000; // Increased to 30 seconds

        if (!this.outputElement || !this.inputElement) {
            console.error('Console initialization failed: Missing required elements');
            throw new Error('Console requires valid output and input elements');
        }

        // Initialize Socket.IO with enhanced configuration and logging
        this.socket = io({
            transports: ['websocket'],
            reconnection: true,
            reconnectionAttempts: this.maxReconnectAttempts,
            reconnectionDelay: 1000,
            timeout: this.compilationTimeout
        });

        console.debug('Initializing Interactive Console...');
        this.setupEventHandlers();
        this.clear();
    }

    setupEventHandlers() {
        this.socket.on('connect', () => {
            console.debug('Socket connected successfully');
            this.reconnectAttempts = 0;
            this.appendSystemMessage('Connected to console server');
        });

        this.socket.on('connect_error', (error) => {
            console.error('Socket connection error:', error);
            this.appendError(`Connection error: ${error.message}`);
            this.reconnectAttempts++;
            console.warn(`Reconnection attempt ${this.reconnectAttempts} of ${this.maxReconnectAttempts}`);
            if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                this.appendError('Maximum reconnection attempts reached. Please refresh the page.');
                this.socket.disconnect();
            }
        });

        this.socket.on('disconnect', (reason) => {
            console.warn('Socket disconnected:', reason);
            this.appendSystemMessage(`Disconnected from console server (${reason})`);
            this.disableInput();
        });

        this.socket.on('output', (data) => {
            console.debug('Received output event:', data);
            if (data.error) {
                console.error('Output error:', data.error);
                this.appendError(data.error);
                return;
            }
            if (data.output !== undefined) {
                console.debug('Processing output:', { output: data.output, waiting: data.waiting_for_input });
                this.appendOutput(data.output);
                this.isWaitingForInput = data.waiting_for_input || false;
                this.updateInputState();
            }
        });

        this.socket.on('compilation_result', (data) => {
            console.debug('Received compilation result:', data);
            if (!data.success) {
                console.error('Compilation failed:', data.error);
                this.appendError(`Compilation error: ${data.error}`);
                return;
            }

            if (data.session_id) {
                this.sessionId = data.session_id;
                console.debug(`Session started: ${this.sessionId}`);
                this.appendSystemMessage('Program compiled successfully, waiting for output...');

                // Clear any existing compilation timeout
                if (this.compilationTimeoutId) {
                    clearTimeout(this.compilationTimeoutId);
                    this.compilationTimeoutId = null;
                }
            }
        });

        this.socket.on('error', (data) => {
            console.error('Server error:', data);
            this.appendError(`Server error: ${data.message}`);
        });

        // Input handler with enhanced error logging
        this.inputElement.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleInput();
            }
        });
    }

    async handleInput() {
        if (!this.isEnabled || !this.sessionId) {
            console.debug('Input handler: not enabled or no session', {
                isEnabled: this.isEnabled,
                sessionId: this.sessionId
            });
            return;
        }

        const input = this.inputElement.value.trim();
        if (!input) return;

        try {
            console.debug('Sending input to server:', {
                sessionId: this.sessionId,
                input: input
            });
            this.inputElement.value = '';
            this.appendOutput(`> ${input}\n`, 'console-input');

            this.socket.emit('input', {
                session_id: this.sessionId,
                input: input + '\n'
            });

            this.isWaitingForInput = false;
            this.updateInputState();
        } catch (error) {
            console.error('Input handler error:', error);
            this.appendError(`Failed to send input: ${error.message}`);
        }
    }

    appendOutput(text, className = '') {
        console.debug('Appending output:', { text, className });
        const line = document.createElement('div');
        line.className = `console-line ${className}`;
        line.textContent = text;
        this.outputElement.appendChild(line);
        this.scrollToBottom();
    }

    appendError(message) {
        console.error('Console error:', message);
        this.appendOutput(`Error: ${message}\n`, 'console-error');
    }

    appendSystemMessage(message) {
        console.debug('System message:', message);
        this.appendOutput(`System: ${message}\n`, 'console-system');
    }

    clear() {
        console.debug('Clearing console');
        this.outputElement.innerHTML = '';
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.updateInputState();
    }

    scrollToBottom() {
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    enableInput() {
        console.debug('Enabling console input');
        this.isEnabled = true;
        this.inputElement.disabled = false;
        this.inputElement.placeholder = 'Enter input...';
        this.inputElement.classList.remove('console-disabled');
        this.inputElement.focus();
    }

    disableInput() {
        console.debug('Disabling console input');
        this.isEnabled = false;
        this.inputElement.disabled = true;
        this.inputElement.placeholder = 'Console disconnected';
        this.inputElement.classList.add('console-disabled');
    }

    updateInputState() {
        console.debug('Updating input state:', {
            isWaitingForInput: this.isWaitingForInput,
            sessionId: this.sessionId
        });
        if (this.isWaitingForInput) {
            this.enableInput();
        } else {
            this.disableInput();
        }
    }

    compileAndRun(code) {
        console.debug('Compiling and running code:', {
            codeLength: code.length,
            language: this.currentLanguage
        });
        this.clear();
        this.appendSystemMessage('Compiling and running program...');

        // Clear any existing session
        this.sessionId = null;
        this.isWaitingForInput = false;

        // Set compilation timeout handler
        if (this.compilationTimeoutId) {
            clearTimeout(this.compilationTimeoutId);
        }

        this.compilationTimeoutId = setTimeout(() => {
            if (!this.sessionId) {
                console.error('Compilation timeout - no response received');
                this.appendError('Compilation timeout - no response received from server. This might be due to high server load or a complex compilation. Please try again.');
                // Attempt to reconnect socket
                if (this.socket.connected) {
                    this.socket.disconnect().connect();
                }
            }
        }, this.compilationTimeout);

        this.socket.emit('compile_and_run', {
            code,
            language: this.currentLanguage
        });
    }
}

// Export for browser environments
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}