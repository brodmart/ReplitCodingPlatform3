/**
 * Interactive Console for handling program I/O
 */
class InteractiveConsole {
    constructor() {
        // Wait for DOM to be fully loaded
        document.addEventListener('DOMContentLoaded', () => {
            this.init();
        });
    }

    init() {
        // Get DOM elements
        this.outputElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');

        if (!this.outputElement || !this.inputElement) {
            console.error('Waiting for DOM elements...');
            return;
        }

        // Clear and show initial message
        this.outputElement.innerHTML = '<div class="console-loading">Initializing console...</div>';

        // Initialize socket
        this.socket = io({
            transports: ['websocket']
        });

        // Basic socket setup
        this.socket.on('connect', () => {
            this.log('Connected to server');
            this.inputElement.disabled = false;
        });

        this.socket.on('disconnect', () => {
            this.log('Disconnected from server');
            this.inputElement.disabled = true;
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

    sendInput(input) {
        if (!this.socket?.connected) return;
        this.inputElement.value = '';
        this.log(`> ${input}`);
        this.socket.emit('input', {
            input: input + '\n'
        });
    }

    compileAndRun(code) {
        if (!this.socket?.connected) {
            this.error('Not connected to server');
            return;
        }
        this.clear();
        this.log('Running code...');
        this.socket.emit('compile_and_run', { code });
    }

    clear() {
        if (this.outputElement) {
            this.outputElement.innerHTML = '';
        }
    }

    scrollToBottom() {
        if (this.outputElement) {
            this.outputElement.scrollTop = this.outputElement.scrollHeight;
        }
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