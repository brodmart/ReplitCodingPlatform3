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
            throw new Error('Console not fully initialized');
        }

        // Setup socket connection
        this.socket = io({
            transports: ['websocket'],
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: 5
        });

        // Socket event handlers
        this.socket.on('connect', () => {
            console.log('Socket connected successfully');
            this.log('Connected to console server');
        });

        this.socket.on('disconnect', () => {
            console.log('Socket disconnected');
            this.log('Disconnected from console server');
        });

        this.socket.on('connect_error', (error) => {
            console.error('Socket connection error:', error);
            this.error('Connection error: ' + error.message);
        });

        this.socket.on('console_output', (data) => {
            console.log('Received output:', data);
            if (data.error) {
                this.error(data.error);
            } else if (data.output) {
                this.log(data.output);
            }
        });

        console.log('Console initialization completed');
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