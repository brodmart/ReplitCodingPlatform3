/**
 * Interactive Console class for handling real-time program I/O using CodeMirror
 */
class InteractiveConsole {
    constructor() {
        this.outputBuffer = [];
        this.inputHistory = [];
        this.historyIndex = -1;
        this.currentInput = '';
        this.isEnabled = true;

        // Initialize DOM elements
        this.consoleElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');

        if (!this.consoleElement || !this.inputElement) {
            throw new Error('Console elements not found');
        }

        // Initialize console state
        this.setupEventListeners();
        this.clear();
        this.enable();
    }

    setupEventListeners() {
        // Input handling
        this.inputElement.addEventListener('keydown', (e) => {
            if (!this.isEnabled) return;

            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const input = this.inputElement.value.trim();
                if (input) {
                    this.handleInput(input);
                }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this.navigateHistory(-1);
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                this.navigateHistory(1);
            }
        });

        // Clear button
        const clearButton = document.getElementById('clearConsole');
        if (clearButton) {
            clearButton.addEventListener('click', () => this.clear());
        }
    }

    navigateHistory(direction) {
        if (!this.inputHistory.length) return;

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

        if (typeof text === 'object') {
            line.textContent = JSON.stringify(text, null, 2);
        } else {
            line.textContent = String(text);
        }

        this.consoleElement.appendChild(line);
        this.consoleElement.scrollTop = this.consoleElement.scrollHeight;
        this.outputBuffer.push({ text, className });
    }

    handleInput(input) {
        if (!this.isEnabled) return;

        // Add to history if not empty and different from last entry
        if (input && (!this.inputHistory.length || this.inputHistory[this.inputHistory.length - 1] !== input)) {
            this.inputHistory.push(input);
        }

        // Reset history navigation
        this.historyIndex = -1;

        // Echo input with prompt
        this.appendOutput(`> ${input}`, 'input');

        // Clear input field
        this.inputElement.value = '';

        // Handle special commands
        if (input.toLowerCase() === 'clear') {
            this.clear();
            return;
        }
    }

    setError(message) {
        this.appendOutput(message, 'error');
    }

    setSuccess(message) {
        this.appendOutput(message, 'success');
    }

    clear() {
        if (this.consoleElement) {
            this.consoleElement.innerHTML = '';
            this.outputBuffer = [];
        }
    }

    enable() {
        this.isEnabled = true;
        if (this.inputElement) {
            this.inputElement.disabled = false;
            this.inputElement.placeholder = "Type commands here...";
            this.inputElement.focus();
        }
    }

    disable() {
        this.isEnabled = false;
        if (this.inputElement) {
            this.inputElement.disabled = true;
            this.inputElement.placeholder = "Console is disabled...";
        }
    }

    getOutputBuffer() {
        return this.outputBuffer;
    }
}

// Export to window object
window.InteractiveConsole = InteractiveConsole;