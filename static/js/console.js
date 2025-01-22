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

        if (!this.outputElement || !this.inputElement) {
            throw new Error('Console requires valid output and input elements');
        }

        // Initialize Socket.IO with enhanced configuration
        this.socket = io({
            transports: ['websocket'],
            reconnection: true,
            reconnectionAttempts: this.maxReconnectAttempts,
            reconnectionDelay: 1000,
            timeout: 10000
        });

        this.setupEventHandlers();
        this.clear();
    }

    setupEventHandlers() {
        this.socket.on('connect', () => {
            console.debug('Socket connected');
            this.reconnectAttempts = 0;
            this.appendSystemMessage('Connected to console server');
        });

        this.socket.on('connect_error', (error) => {
            console.error('Socket connection error:', error);
            this.appendError(`Connection error: ${error.message}`);
            this.reconnectAttempts++;
            if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                this.appendError('Maximum reconnection attempts reached. Please refresh the page.');
                this.socket.disconnect();
            }
        });

        this.socket.on('disconnect', () => {
            console.debug('Socket disconnected');
            this.appendSystemMessage('Disconnected from console server');
            this.disableInput();
        });

        this.socket.on('output', (data) => {
            console.debug('Received output:', data);
            if (data.error) {
                this.appendError(data.error);
                return;
            }
            if (data.output !== undefined) {
                this.appendOutput(data.output);
                this.isWaitingForInput = data.waiting_for_input || false;
                this.updateInputState();
            }
        });

        this.socket.on('compilation_result', (data) => {
            console.debug('Received compilation result:', data);
            if (!data.success) {
                this.appendError(`Compilation error: ${data.error}`);
                return;
            }

            if (data.session_id) {
                this.sessionId = data.session_id;
                console.debug(`Session started: ${this.sessionId}`);
                this.appendSystemMessage('Program compiled successfully, waiting for output...');
            }
        });

        this.socket.on('error', (data) => {
            console.error('Server error:', data);
            this.appendError(`Server error: ${data.message}`);
        });

        // Input handler
        this.inputElement.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleInput();
            }
        });
    }

    async handleInput() {
        if (!this.isEnabled || !this.sessionId) {
            console.debug('Input handler: not enabled or no session');
            return;
        }

        const input = this.inputElement.value.trim();
        if (!input) return;

        try {
            console.debug('Sending input:', input);
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
        this.outputElement.innerHTML = '';
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.updateInputState();
    }

    scrollToBottom() {
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    enableInput() {
        this.isEnabled = true;
        this.inputElement.disabled = false;
        this.inputElement.placeholder = 'Enter input...';
        this.inputElement.classList.remove('console-disabled');
        this.inputElement.focus();
    }

    disableInput() {
        this.isEnabled = false;
        this.inputElement.disabled = true;
        this.inputElement.placeholder = 'Console disconnected';
        this.inputElement.classList.add('console-disabled');
    }

    updateInputState() {
        if (this.isWaitingForInput) {
            this.enableInput();
        } else {
            this.disableInput();
        }
    }

    compileAndRun(code) {
        console.debug('Compiling and running code:', { code, language: this.currentLanguage });
        this.clear();
        this.appendSystemMessage('Compiling and running program...');

        // Clear any existing session
        this.sessionId = null;
        this.isWaitingForInput = false;

        this.socket.emit('compile_and_run', {
            code,
            language: this.currentLanguage
        });

        // Set a timeout to detect if we don't get a response
        setTimeout(() => {
            if (!this.sessionId) {
                console.error('Compilation timeout - no response received');
                this.appendError('Compilation timeout - no response received from server');
            }
        }, 10000);
    }
}

// Export for browser environments
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}