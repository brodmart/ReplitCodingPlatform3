/**
 * Interactive Console for handling program I/O
 * Simplified version with core functionalities
 */
class InteractiveConsole {
    constructor() {
        // Initialize console elements
        this.outputElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');
        this.isWaitingForInput = false;

        // Basic error checking for required elements
        if (!this.outputElement || !this.inputElement) {
            console.error('Required console elements not found. Ensure consoleOutput and consoleInput elements exist.');
            return;
        }

        // Initialize socket connection
        this.socket = io({
            transports: ['websocket'],
            reconnection: true
        });

        this.setupSocketHandlers();
        this.setupInputHandler();
        this.log('Console initialized');
    }

    setupSocketHandlers() {
        this.socket.on('connect', () => {
            this.log('Connected to server');
            this.inputElement.disabled = true;
        });

        this.socket.on('disconnect', () => {
            this.log('Disconnected from server');
            this.inputElement.disabled = true;
            this.isWaitingForInput = false;
        });

        this.socket.on('output', (data) => {
            if (data.error) {
                this.error(data.error);
                return;
            }
            if (data.output) {
                this.log(data.output);
            }
            this.isWaitingForInput = data.waiting_for_input || false;
            this.inputElement.disabled = !this.isWaitingForInput;
            if (this.isWaitingForInput) {
                this.inputElement.focus();
            }
        });
    }

    setupInputHandler() {
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
        line.textContent = `Error: ${message}`;
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

        this.clear();
        this.log('Compiling and running code...');
        this.socket.emit('compile_and_run', { code, language: 'csharp' });
    }
}

// Export for global access
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}