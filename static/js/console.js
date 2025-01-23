/**
 * Interactive Console for handling program I/O
 */
class InteractiveConsole {
    constructor() {
        console.log('Starting console initialization');

        // Get elements
        this.outputElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');

        if (!this.outputElement || !this.inputElement) {
            throw new Error('Console elements not found');
        }

        // Setup socket connection
        this.socket = io({
            transports: ['websocket'],
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: 5
        });

        // Initialize state
        this.isWaitingForInput = false;
        this.setupSocketHandlers();
        this.setupInputHandler();

        console.log('Console initialization completed');
    }

    setupSocketHandlers() {
        // Connection events
        this.socket.on('connect', () => {
            console.log('Socket connected successfully');
            this.log('Connected to console server');
            this.inputElement.disabled = true;
        });

        this.socket.on('disconnect', () => {
            console.log('Socket disconnected');
            this.log('Disconnected from console server');
            this.inputElement.disabled = true;
            this.isWaitingForInput = false;
        });

        this.socket.on('connect_error', (error) => {
            console.error('Socket connection error:', error);
            this.error('Connection error: ' + error.message);
            this.inputElement.disabled = true;
        });

        // Compilation events
        this.socket.on('compilation_result', (data) => {
            console.log('Compilation result:', data);
            if (!data.success) {
                this.error(data.error || 'Compilation failed');
                this.inputElement.disabled = true;
                return;
            }
            this.log('Code compiled successfully');
        });

        // Output events
        this.socket.on('output', (data) => {
            console.log('Received output:', data);
            if (data.error) {
                this.error(data.error);
                return;
            }
            if (data.output) {
                this.log(data.output);
            }
            this.isWaitingForInput = data.waiting_for_input;
            this.inputElement.disabled = !this.isWaitingForInput;
            if (this.isWaitingForInput) {
                this.inputElement.focus();
            }
        });

        this.socket.on('console_output', (data) => {
            console.log('Received console output:', data);
            if (data.output) {
                this.log(data.output);
            }
            this.isWaitingForInput = data.waiting_for_input;
            this.inputElement.disabled = !this.isWaitingForInput;
            if (this.isWaitingForInput) {
                this.inputElement.focus();
            }
        });

        this.socket.on('error', (data) => {
            console.error('Received error:', data);
            this.error(data.message || 'An error occurred');
            this.inputElement.disabled = true;
        });
    }

    setupInputHandler() {
        this.inputElement.addEventListener('keypress', (event) => {
            if (event.key === 'Enter' && !this.inputElement.disabled) {
                const input = this.inputElement.value;
                if (input.trim()) {
                    console.log('Sending input:', input);
                    this.socket.emit('input', { input });
                    this.log(`> ${input}`);
                    this.inputElement.value = '';
                    this.inputElement.disabled = true;
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
        line.textContent = message;
        this.outputElement.appendChild(line);
        this.scrollToBottom();
    }

    scrollToBottom() {
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    clear() {
        this.outputElement.innerHTML = '';
        this.inputElement.disabled = true;
        this.isWaitingForInput = false;
    }

    compileAndRun(code) {
        if (!this.socket.connected) {
            this.error('Not connected to server');
            return;
        }

        console.log('Compiling and running code:', { 
            codeLength: code.length,
            language: 'csharp'
        });

        this.clear();
        this.log('Running code...');

        this.socket.emit('compile_and_run', { 
            code,
            language: 'csharp'
        });
    }
}

// Export for global access
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}