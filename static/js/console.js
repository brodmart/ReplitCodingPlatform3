/**
 * Minimal Interactive Console for handling program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.outputElement = options.outputElement || document.getElementById('console-output');
        this.inputElement = options.inputElement || document.getElementById('console-input');
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;

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
        // Socket.IO event handlers with enhanced error handling
        this.socket.on('connect', () => {
            this.reconnectAttempts = 0;
            this.appendSystemMessage('Connected to console server');
            this.enableInput();
        });

        this.socket.on('connect_error', (error) => {
            this.appendError(`Connection error: ${error.message}`);
            this.reconnectAttempts++;
            if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                this.appendError('Maximum reconnection attempts reached. Please refresh the page.');
                this.socket.disconnect();
            }
        });

        this.socket.on('disconnect', () => {
            this.appendSystemMessage('Disconnected from console server');
            this.disableInput();
        });

        this.socket.on('output', (data) => {
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
            if (!data.success) {
                this.appendError(`Compilation failed: ${data.error}`);
                return;
            }
            if (data.session_id) {
                this.sessionId = data.session_id;
                this.appendSystemMessage('Compilation successful');
            }
        });

        this.socket.on('error', (data) => {
            this.appendError(`Server error: ${data.message}`);
            this.disableInput();
        });

        // Input handler with debouncing
        let inputTimeout;
        this.inputElement.addEventListener('keydown', async (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                clearTimeout(inputTimeout);
                inputTimeout = setTimeout(() => this.handleInput(), 100);
            }
        });
    }

    async handleInput() {
        if (!this.isEnabled || !this.sessionId) return;

        const input = this.inputElement.value.trim();
        if (!input) return;

        try {
            this.inputElement.value = '';
            this.appendOutput(`> ${input}\n`, 'console-input');

            this.socket.emit('input', {
                session_id: this.sessionId,
                input: input + '\n'
            });

            this.isWaitingForInput = false;
            this.updateInputState();
        } catch (error) {
            this.appendError(`Failed to send input: ${error.message}`);
        }
    }

    appendOutput(text, className = 'console-output') {
        const element = document.createElement('div');
        element.className = className;
        element.textContent = text;
        this.outputElement.appendChild(element);
        this.scrollToBottom();
    }

    appendError(message) {
        this.appendOutput(`Error: ${message}\n`, 'console-error');
    }

    appendSystemMessage(message) {
        this.appendOutput(`System: ${message}\n`, 'console-system');
    }

    clear() {
        this.outputElement.innerHTML = '';
        this.sessionId = null;
        this.isWaitingForInput = false;
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
}

// Export for browser environments
if (typeof window !== 'undefined') {
    window.MyInteractiveConsole = InteractiveConsole;
}