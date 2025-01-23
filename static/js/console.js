/**
 * Interactive Console for handling program I/O
 * Core implementation with essential functionality
 */
class InteractiveConsole {
    constructor() {
        this.outputElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');

        if (!this.outputElement || !this.inputElement) {
            throw new Error('Console elements not found');
        }

        // Initialize socket connection with retry logic
        this.socket = io({
            transports: ['websocket'],
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000
        });

        this.setupEventHandlers();
        this.log('Console initialized and ready');
    }

    setupEventHandlers() {
        // Socket event handlers
        this.socket.on('connect', () => {
            this.log('Connected to server');
            this.inputElement.disabled = true;
        });

        this.socket.on('disconnect', () => {
            this.log('Disconnected from server');
            this.inputElement.disabled = true;
        });

        this.socket.on('output', (data) => {
            if (data.error) {
                this.error(data.error);
                return;
            }
            if (data.output) {
                this.log(data.output);
            }
            // Enable input if program is waiting for it
            this.inputElement.disabled = !data.waiting_for_input;
            if (data.waiting_for_input) {
                this.inputElement.focus();
            }
        });

        // Input handler
        this.inputElement.addEventListener('keypress', (event) => {
            if (event.key === 'Enter' && !this.inputElement.disabled) {
                const input = this.inputElement.value.trim();
                if (input) {
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
        line.textContent = message;
        this.outputElement.appendChild(line);
        this.scrollToBottom();
    }

    error(message) {
        const line = document.createElement('div');
        line.style.color = '#ff5555';
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
    }

    compileAndRun(code) {
        if (!this.socket || !this.socket.connected) {
            this.error('Not connected to server');
            return;
        }

        this.clear();
        this.log('Compiling and running code...');
        this.socket.emit('compile_and_run', { 
            code,
            language: 'csharp'  // Default to C# for now
        });
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}