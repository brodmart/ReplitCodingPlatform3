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
        this.isWaitingForInput = false;

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
        try {
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
        } catch (error) {
            console.error('Failed to set up event listeners:', error);
            throw error;
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
        try {
            if (!this.consoleElement) {
                throw new Error('Console output element not found');
            }

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
        } catch (error) {
            console.error('Error appending output:', error);
        }
    }

    handleInput(input) {
        if (!this.isEnabled) return;

        try {
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
        } catch (error) {
            console.error('Error handling input:', error);
            this.setError('Failed to process input');
        }
    }

    setError(message) {
        this.appendOutput(message, 'error');
    }

    setSuccess(message) {
        this.appendOutput(message, 'success');
    }

    clear() {
        try {
            if (!this.consoleElement) {
                throw new Error('Console element not found');
            }
            this.consoleElement.innerHTML = '';
            this.outputBuffer = [];
        } catch (error) {
            console.error('Error clearing console:', error);
        }
    }

    enable() {
        try {
            if (!this.inputElement) {
                throw new Error('Input element not found');
            }
            this.isEnabled = true;
            this.inputElement.disabled = false;
            this.inputElement.placeholder = "Type commands here...";
            this.inputElement.focus();
        } catch (error) {
            console.error('Error enabling console:', error);
        }
    }

    disable() {
        try {
            if (!this.inputElement) {
                throw new Error('Input element not found');
            }
            this.isEnabled = false;
            this.inputElement.disabled = true;
            this.inputElement.placeholder = "Console is disabled...";
        } catch (error) {
            console.error('Error disabling console:', error);
        }
    }

    getOutputBuffer() {
        return this.outputBuffer;
    }
}

// Export to window object
window.InteractiveConsole = InteractiveConsole;