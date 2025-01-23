/**
 * Interactive Console for handling program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        // Basic initialization
        this.outputElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');
        this.language = options.language || 'csharp';

        if (!this.outputElement || !this.inputElement) {
            console.error('Console elements not found');
            return;
        }

        // Initialize socket connection
        this.socket = io({
            transports: ['websocket']
        });

        // Socket connection handlers
        this.socket.on('connect', () => {
            this.log('Connected to server');
            this.enable();
        });

        this.socket.on('disconnect', () => {
            this.log('Disconnected from server');
            this.disable();
        });

        // Program output handler
        this.socket.on('console_output', (data) => {
            if (data.error) {
                this.error(data.error);
            } else if (data.output) {
                this.log(data.output);
            }
            this.inputElement.disabled = !data.waiting_for_input;
        });

        // Input handler
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
        this.clear();
        this.log('Console ready');
    }

    compileAndRun(code) {
        if (!this.socket?.connected) {
            this.error('Not connected to server');
            return;
        }

        this.clear();
        this.log('Running code...');

        this.socket.emit('compile_and_run', {
            code: code,
            language: this.language
        });
    }

    sendInput(input) {
        this.inputElement.value = '';
        this.log(`> ${input}`);

        this.socket.emit('input', {
            input: input + '\n',
            language: this.language
        });
    }

    log(message) {
        const line = document.createElement('div');
        line.className = 'console-line';
        line.textContent = message;
        this.outputElement.appendChild(line);
        this.scrollToBottom();
    }

    error(message) {
        const line = document.createElement('div');
        line.className = 'console-line console-error';
        line.textContent = `Error: ${message}`;
        this.outputElement.appendChild(line);
        this.scrollToBottom();
    }

    enable() {
        this.inputElement.disabled = false;
        this.inputElement.placeholder = 'Enter input...';
    }

    disable() {
        this.inputElement.disabled = true;
        this.inputElement.placeholder = 'Console inactive';
    }

    clear() {
        this.outputElement.innerHTML = '';
    }

    scrollToBottom() {
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