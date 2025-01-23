/**
 * Interactive Console for handling program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        // Store DOM elements from options
        this.outputElement = options.outputElement;
        this.inputElement = options.inputElement;
        this.language = options.language || 'csharp';

        if (!this.outputElement || !this.inputElement) {
            throw new Error('Console elements not provided');
        }

        // Initialize state
        this.initialized = false;
        this.init();
    }

    async init() {
        try {
            // Clear console and show initial message
            this.clear();
            this.log('Initializing console...');

            // Initialize socket connection
            this.socket = io({
                transports: ['websocket']
            });

            // Socket event handlers
            this.socket.on('connect', () => {
                this.log('Connected to server');
                this.initialized = true;
                this.enable();
            });

            this.socket.on('disconnect', () => {
                this.log('Disconnected from server');
                this.disable();
            });

            // Handle program output
            this.socket.on('console_output', (data) => {
                if (data.error) {
                    this.error(data.error);
                } else if (data.output) {
                    this.log(data.output);
                }
                this.inputElement.disabled = !data.waiting_for_input;
            });

            // Setup input handler
            this.inputElement.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    const input = this.inputElement.value.trim();
                    if (input) {
                        this.sendInput(input);
                    }
                }
            });

            // Show ready state
            this.log('Console ready');

        } catch (error) {
            this.error(`Initialization failed: ${error.message}`);
            console.error('Console initialization error:', error);
        }
    }

    log(message) {
        if (!this.outputElement) return;
        const line = document.createElement('div');
        line.className = 'console-line';
        line.textContent = message;
        this.outputElement.appendChild(line);
        this.scrollToBottom();
    }

    error(message) {
        if (!this.outputElement) return;
        const line = document.createElement('div');
        line.className = 'console-line console-error';
        line.textContent = `Error: ${message}`;
        this.outputElement.appendChild(line);
        this.scrollToBottom();
    }

    sendInput(input) {
        if (!this.initialized || !this.socket?.connected) return;
        this.inputElement.value = '';
        this.log(`> ${input}`);
        this.socket.emit('input', {
            input: input + '\n'
        });
    }

    compileAndRun(code) {
        if (!this.initialized || !this.socket?.connected) {
            this.error('Console not ready');
            return;
        }
        this.clear();
        this.log('Running code...');
        this.socket.emit('compile_and_run', {
            code,
            language: this.language
        });
    }

    enable() {
        if (!this.inputElement) return;
        this.inputElement.disabled = false;
        this.inputElement.placeholder = 'Enter input...';
    }

    disable() {
        if (!this.inputElement) return;
        this.inputElement.disabled = true;
        this.inputElement.placeholder = 'Console inactive';
    }

    clear() {
        if (!this.outputElement) return;
        this.outputElement.innerHTML = '';
    }

    scrollToBottom() {
        if (!this.outputElement) return;
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }
}

// Export for global access
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.consoleInstance?.socket) {
        window.consoleInstance.socket.disconnect();
    }
});