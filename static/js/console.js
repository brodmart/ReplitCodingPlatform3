/**
 * Simple Interactive Console Implementation
 */
class InteractiveConsole {
    constructor() {
        this.outputElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');
        this.currentSessionId = null;

        if (!this.outputElement || !this.inputElement) {
            throw new Error('Console elements not found');
        }

        this.socket = io();
        this.setupSocketEvents();
        this.setupInputHandler();
    }

    setupSocketEvents() {
        this.socket.on('compilation_success', () => {
            this.log('Program started...');
        });

        this.socket.on('compilation_error', (data) => {
            this.error(data.error || 'Compilation failed');
            this.inputElement.disabled = true;
        });

        this.socket.on('output', (data) => {
            if (data.session_id) {
                this.currentSessionId = data.session_id;
            }
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
                    this.socket.emit('input', { 
                        session_id: this.currentSessionId,
                        input 
                    });
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
        this.currentSessionId = null;
    }

    compileAndRun(code) {
        this.clear();
        this.log('Compiling and running code...');
        this.socket.emit('compile_and_run', { code });
    }
}

// Initialize console when DOM is ready
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}