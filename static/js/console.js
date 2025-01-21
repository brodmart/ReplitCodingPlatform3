/**
 * Interactive Console class for handling real-time program I/O using Xterm.js
 */
class InteractiveConsole {
    constructor() {
        console.log('Initializing InteractiveConsole');
        this.outputBuffer = [];
        this.inputHistory = [];
        this.historyIndex = -1;
        this.currentInput = '';
        this.isWaitingForInput = false;
        this.inputCallback = null;
        this.consoleElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');

        // Initialize console if elements exist
        if (this.consoleElement && this.inputElement) {
            this.setupEventListeners();
            this.clear();
        } else {
            console.error('Console elements not found');
        }
    }

    setupEventListeners() {
        if (!this.inputElement) return;

        this.inputElement.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && this.isWaitingForInput) {
                e.preventDefault();
                const input = this.inputElement.value;
                this.handleInput(input);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this.navigateHistory(-1);
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                this.navigateHistory(1);
            }
        });

        // Clear console button handler
        const clearButton = document.getElementById('clearConsole');
        if (clearButton) {
            clearButton.addEventListener('click', () => this.clear());
        }
    }

    navigateHistory(direction) {
        if (!this.inputElement || this.inputHistory.length === 0) return;

        if (this.historyIndex === -1) {
            this.currentInput = this.inputElement.value;
        }

        this.historyIndex += direction;

        if (this.historyIndex >= this.inputHistory.length) {
            this.historyIndex = this.inputHistory.length - 1;
        } else if (this.historyIndex < -1) {
            this.historyIndex = -1;
        }

        this.inputElement.value = this.historyIndex === -1 ? 
            this.currentInput : 
            this.inputHistory[this.historyIndex];
    }

    appendOutput(text, className = '') {
        if (!this.consoleElement) return;

        const line = document.createElement('div');
        line.className = `console-line ${className}`;
        line.textContent = text;
        this.consoleElement.appendChild(line);
        this.consoleElement.scrollTop = this.consoleElement.scrollHeight;
        this.outputBuffer.push({ text, className });
    }

    handleInput(input) {
        if (!this.isWaitingForInput || !this.inputElement) return;

        // Add to history if not empty and different from last entry
        if (input && (!this.inputHistory.length || this.inputHistory[this.inputHistory.length - 1] !== input)) {
            this.inputHistory.push(input);
        }

        // Reset history navigation
        this.historyIndex = -1;

        // Echo input
        this.appendOutput(`> ${input}`, 'console-input');

        // Clear input field
        this.inputElement.value = '';

        // Call callback if exists
        if (this.inputCallback) {
            this.inputCallback(input);
            this.inputCallback = null;
        }

        this.isWaitingForInput = false;
    }

    async getInput(prompt = '> ') {
        if (!this.inputElement) return null;

        this.appendOutput(prompt, 'console-prompt');
        this.isWaitingForInput = true;
        this.inputElement.focus();

        return new Promise(resolve => {
            this.inputCallback = resolve;
        });
    }

    setError(message) {
        this.appendOutput(message, 'console-error');
    }

    setSuccess(message) {
        this.appendOutput(message, 'console-success');
    }

    clear() {
        if (this.consoleElement) {
            this.consoleElement.innerHTML = '';
            this.outputBuffer = [];
        }
    }

    disable() {
        if (this.inputElement) {
            this.inputElement.disabled = true;
        }
    }

    enable() {
        if (this.inputElement) {
            this.inputElement.disabled = false;
            this.inputElement.focus();
        }
    }
}

// Export the console to window object
window.InteractiveConsole = InteractiveConsole;