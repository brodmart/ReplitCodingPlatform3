/**
 * Simplified Interactive Console class for handling real-time program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.outputElement = options.outputElement || document.getElementById('consoleOutput');
        this.inputElement = options.inputElement || document.getElementById('consoleInput');
        this.language = options.language || 'cpp';
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.history = [];
        this.historyIndex = -1;

        if (!this.outputElement || !this.inputElement) {
            throw new Error('Console requires output and input elements');
        }

        // Initialize Socket.IO with minimal configuration
        this.socket = io({
            transports: ['websocket'],
            reconnection: true,
            reconnectionAttempts: 3
        });

        this.setupEventHandlers();
        this.clear();
    }

    setupEventHandlers() {
        // Socket.IO event handlers
        this.socket.on('connect', () => {
            console.debug('Connected to server');
            this.appendSystemMessage('Connected to console');
            this.enableInput();
        });

        this.socket.on('disconnect', () => {
            console.debug('Disconnected from server');
            this.appendSystemMessage('Disconnected from console');
            this.disableInput();
        });

        this.socket.on('output', (data) => {
            if (data.error) {
                this.appendError(data.error);
                return;
            }
            if (data.output) {
                this.appendOutput(data.output);
                this.isWaitingForInput = data.waiting_for_input || false;
                this.updateInputState();
            }
        });

        // Input handlers
        this.inputElement.addEventListener('keydown', async (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                await this.handleInput();
            }
        });
    }

    async handleInput() {
        if (!this.isEnabled || !this.sessionId) return;

        const input = this.inputElement.value.trim();
        if (!input) return;

        this.inputElement.value = '';
        this.appendOutput(`> ${input}\n`, 'console-input');

        this.socket.emit('input', {
            session_id: this.sessionId,
            input: input + '\n'
        });

        this.history.push(input);
        this.historyIndex = this.history.length;
        this.isWaitingForInput = false;
        this.updateInputState();
    }

    appendOutput(text, className = 'console-output') {
        const element = document.createElement('div');
        element.className = `output-line ${className}`;
        element.textContent = text;
        this.outputElement.appendChild(element);
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
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

    enableInput() {
        this.isEnabled = true;
        this.inputElement.disabled = false;
        this.inputElement.placeholder = 'Enter input...';
        this.inputElement.classList.remove('console-disabled');
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
            this.inputElement.focus();
        } else {
            this.disableInput();
        }
    }

    setSession(sessionId) {
        this.sessionId = sessionId;
        if (sessionId) {
            this.clear();
            this.enableInput();
        } else {
            this.disableInput();
        }
    }
}

// Export to window object
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}