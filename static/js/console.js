/**
 * Interactive Console Implementation with improved Socket.IO handling
 */
class InteractiveConsole {
    constructor() {
        this.outputElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');
        this.currentSessionId = null;
        this.connected = false;
        this.waitingForOutput = false;

        if (!this.outputElement || !this.inputElement) {
            throw new Error('Console elements not found');
        }

        this.socket = io({
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: 5
        });

        this.setupSocketEvents();
        this.setupInputHandler();

        // Log initialization
        console.log('Console initialized with elements:', {
            output: this.outputElement,
            input: this.inputElement
        });
    }

    setupSocketEvents() {
        // Connection events
        this.socket.on('connect', () => {
            console.log('Socket connected');
            this.connected = true;
            this.log('Console connected');
            this.inputElement.disabled = false;
        });

        this.socket.on('disconnect', () => {
            console.log('Socket disconnected');
            this.connected = false;
            this.log('Console disconnected. Attempting to reconnect...');
            this.inputElement.disabled = true;
            this.waitingForOutput = false;
        });

        this.socket.on('connect_error', (error) => {
            console.error('Connection error:', error);
            this.error(`Connection error: ${error.message}`);
            this.inputElement.disabled = true;
            this.waitingForOutput = false;
        });

        // Compilation events
        this.socket.on('compilation_success', (data) => {
            console.log('Compilation success:', data);
            if (data && data.session_id) {
                this.currentSessionId = data.session_id;
            }
            this.log('Program started successfully...');
        });

        this.socket.on('compilation_error', (data) => {
            console.error('Compilation error:', data);
            this.error(data.error || 'Compilation failed');
            this.inputElement.disabled = true;
            this.currentSessionId = null;
            this.waitingForOutput = false;
        });

        // Output events
        this.socket.on('output', (data) => {
            console.log('Received output:', data);
            if (!data) return;

            if (data.session_id) {
                this.currentSessionId = data.session_id;
            }

            if (data.output) {
                this.log(data.output, false);
            }

            this.waitingForOutput = false;
            this.inputElement.disabled = !data.waiting_for_input;

            if (data.waiting_for_input) {
                console.log('Enabling input for user');
                this.inputElement.focus();
            } else {
                console.log('Input disabled, not waiting for input');
            }
        });

        // Error events
        this.socket.on('error', (data) => {
            console.error('Received error:', data);
            this.error(data.message || 'An error occurred');
            this.inputElement.disabled = true;
            this.waitingForOutput = false;
        });
    }

    setupInputHandler() {
        this.inputElement.addEventListener('keypress', (event) => {
            if (event.key === 'Enter' && !this.inputElement.disabled && !this.waitingForOutput) {
                const input = this.inputElement.value.trim();
                if (input === null || input === '') return;

                if (!this.currentSessionId) {
                    this.error('No active session');
                    return;
                }

                console.log('Sending input:', input);
                this.waitingForOutput = true;
                this.socket.emit('input', {
                    session_id: this.currentSessionId,
                    input
                });

                this.log(`> ${input}`);
                this.inputElement.value = '';
                this.inputElement.disabled = true;
            }
        });
    }

    log(message, addNewLine = true) {
        console.log('Console output:', message);
        const line = document.createElement('div');
        line.textContent = message + (addNewLine ? '\n' : '');
        this.outputElement.appendChild(line);
        this.scrollToBottom();
    }

    error(message) {
        console.error('Console error:', message);
        const line = document.createElement('div');
        line.className = 'error-message';
        line.textContent = `Error: ${message}`;
        this.outputElement.appendChild(line);
        this.scrollToBottom();
    }

    scrollToBottom() {
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    clear() {
        this.outputElement.innerHTML = '';
        this.currentSessionId = null;
        this.inputElement.disabled = true;
        this.waitingForOutput = false;
    }

    compileAndRun(code) {
        if (!this.connected) {
            this.error('Not connected to server');
            return;
        }

        console.log('Compiling code:', code);
        this.clear();
        this.log('Compiling and running code...');
        this.socket.emit('compile_and_run', { code });
    }
}

// Initialize console when DOM is ready
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}