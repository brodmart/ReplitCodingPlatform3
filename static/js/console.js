/**
 * Interactive Console for handling program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.outputElement = options.outputElement || document.getElementById('console-output');
        this.inputElement = options.inputElement || document.getElementById('console-input');
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.currentLanguage = 'csharp';
        this.compilationTimeout = 60000; // 60s timeout

        if (!this.outputElement || !this.inputElement) {
            console.error('Console initialization failed: Missing required elements');
            throw new Error('Console requires valid output and input elements');
        }

        console.debug('Initializing Interactive Console...');
        this.setupSocket();
        this.setupEventHandlers();
        this.clear();
    }

    setupSocket() {
        // Initialize Socket.IO with simple configuration
        this.socket = io({
            transports: ['websocket'],
            reconnection: true,
            reconnectionAttempts: 3,
            timeout: this.compilationTimeout
        });

        this.socket.on('connect', () => {
            console.debug('Socket connected');
            this.appendSystemMessage('Connected to server');
        });

        this.socket.on('disconnect', () => {
            console.debug('Socket disconnected');
            this.appendSystemMessage('Disconnected from server');
            this.disableInput();
        });

        this.socket.on('error', (error) => {
            console.error('Socket error:', error);
            this.appendError(`Server error: ${error.message}`);
            this.disableInput();
        });
    }

    setupEventHandlers() {
        this.socket.on('output', (data) => {
            console.debug('Received output:', data);

            if (data.error) {
                this.appendError(data.error);
                return;
            }

            if (data.output) {
                this.appendOutput(data.output);
            }

            // Update input state based on server's indication
            this.isWaitingForInput = data.waiting_for_input;
            this.updateInputState();
        });

        this.socket.on('compilation_result', (data) => {
            console.debug('Compilation result:', data);

            if (!data.success) {
                this.appendError(`Compilation failed: ${data.error}`);
                return;
            }

            if (data.session_id) {
                this.sessionId = data.session_id;
                this.appendSystemMessage('Program started successfully');

                // Enable input for interactive sessions
                if (data.interactive) {
                    this.isWaitingForInput = true;
                    this.updateInputState();
                }
            }
        });

        // Input handler
        this.inputElement.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleInput();
            }
        });
    }

    handleInput() {
        if (!this.isEnabled || !this.sessionId) {
            console.debug('Input handler: disabled or no session');
            return;
        }

        const input = this.inputElement.value.trim();
        if (!input) return;

        console.debug('Sending input:', input);
        this.inputElement.value = '';
        this.appendOutput(`> ${input}\n`, 'console-input');

        this.socket.emit('input', {
            session_id: this.sessionId,
            input: input
        });

        this.isWaitingForInput = false;
        this.updateInputState();
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
        console.debug('Enabling input');
        this.isEnabled = true;
        this.inputElement.disabled = false;
        this.inputElement.placeholder = 'Enter input...';
        this.inputElement.focus();
    }

    disableInput() {
        console.debug('Disabling input');
        this.isEnabled = false;
        this.inputElement.disabled = true;
        this.inputElement.placeholder = 'Console inactive';
    }

    updateInputState() {
        console.debug('Updating input state:', {
            isWaitingForInput: this.isWaitingForInput,
            sessionId: this.sessionId
        });

        if (this.sessionId && this.isWaitingForInput) {
            this.enableInput();
        } else {
            this.disableInput();
        }
    }

    compileAndRun(code) {
        console.debug('Compiling code:', {
            codeLength: code.length,
            language: this.currentLanguage
        });

        this.clear();
        this.appendSystemMessage('Compiling and running program...');

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