/**
 * Minimal Interactive Console for handling program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.outputElement = options.outputElement || document.getElementById('console-output');
        this.inputElement = options.inputElement || document.getElementById('console-input');
        this.sessionId = null;
        this.isWaitingForInput = false;

        if (!this.outputElement || !this.inputElement) {
            throw new Error('Console requires valid output and input elements');
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
            console.log('Connected to console server');
            this.appendSystemMessage('Connected to console server');
            this.enableInput();
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from console server');
            this.appendSystemMessage('Disconnected from console server');
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

        // Input handler
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
        this.appendOutput(`> ${input}\n`);

        this.socket.emit('input', {
            session_id: this.sessionId,
            input: input + '\n'
        });

        this.isWaitingForInput = false;
        this.updateInputState();
    }

    appendOutput(text, className = 'console-output') {
        const element = document.createElement('div');
        element.className = className;
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

// Export for browser environments
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}