/**
 * Interactive Console Implementation
 * Handles program I/O through Socket.IO
 */
class InteractiveConsole {
    constructor() {
        this.outputElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');

        if (!this.outputElement || !this.inputElement) {
            throw new Error('Console elements not found');
        }

        // Initialize Socket.IO connection
        this.socket = io();
        this.setupSocketEvents();
        this.setupInputHandler();
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            this.log('Connected to server');
            this.inputElement.disabled = false;
        });

        this.socket.on('disconnect', () => {
            this.log('Disconnected from server');
            this.inputElement.disabled = true;
        });

        this.socket.on('compilation_success', () => {
            this.log('Program compiled successfully');
        });

        this.socket.on('compilation_error', (data) => {
            this.error(data.error || 'Compilation failed');
            this.inputElement.disabled = true;
        });

        this.socket.on('output', (data) => {
            if (data.output) {
                this.log(data.output, false);
            }
            this.inputElement.disabled = !data.waiting_for_input;
            if (data.waiting_for_input) {
                this.inputElement.focus();
            }
        });

        this.socket.on('error', (data) => {
            this.error(data.message || 'An error occurred');
            this.inputElement.disabled = true;
        });
    }

    setupInputHandler() {
        this.inputElement.addEventListener('keypress', (event) => {
            if (event.key === 'Enter' && !this.inputElement.disabled) {
                const input = this.inputElement.value;
                if (input !== null) {
                    this.socket.emit('input', { input });
                    this.log(`> ${input}`);
                    this.inputElement.value = '';
                }
            }
        });
    }

    log(message, addNewLine = true) {
        const line = document.createElement('div');
        line.textContent = message + (addNewLine ? '\n' : '');
        this.outputElement.appendChild(line);
        this.scrollToBottom();
    }

    error(message) {
        const line = document.createElement('div');
        line.className = 'error-message';
        line.textContent = message;
        this.outputElement.appendChild(line);
        this.scrollToBottom();
    }

    scrollToBottom() {
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    clear() {
        this.outputElement.innerHTML = '';
    }

    compileAndRun(code) {
        if (!this.socket.connected) {
            this.error('Not connected to server');
            return;
        }

        this.clear();
        this.log('Compiling and running code...');
        this.socket.emit('compile_and_run', { code });
    }
}

// Initialize console when available
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}