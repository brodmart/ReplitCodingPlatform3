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
        this.maxBufferSize = 1000; // Maximum number of lines to keep in buffer

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
                } else if (e.key === 'Tab') {
                    e.preventDefault();
                    this.handleTabCompletion();
                } else if (e.ctrlKey && e.key === 'c') {
                    if (this.isWaitingForInput) {
                        this.handleInterrupt();
                    }
                }
            });

            // Clear button
            const clearButton = document.getElementById('clearConsole');
            if (clearButton) {
                clearButton.addEventListener('click', () => this.clear());
            }

            // Handle paste events
            this.inputElement.addEventListener('paste', (e) => {
                e.preventDefault();
                const text = e.clipboardData.getData('text');
                this.handlePaste(text);
            });

        } catch (error) {
            console.error('Failed to set up event listeners:', error);
            throw error;
        }
    }

    handlePaste(text) {
        // Handle multi-line paste
        const lines = text.split('\n');
        if (lines.length > 1) {
            // If multi-line, execute each line sequentially
            lines.forEach(line => {
                this.inputElement.value = line.trim();
                this.handleInput(line.trim());
            });
        } else {
            // Single line paste
            this.inputElement.value = text;
        }
    }

    handleTabCompletion() {
        // Implement command completion logic here
        const input = this.inputElement.value;
        // Add completion logic based on available commands/context
    }

    handleInterrupt() {
        this.appendOutput('^C', 'interrupt');
        this.isWaitingForInput = false;
        this.enable();
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

        // Move cursor to end of input
        setTimeout(() => {
            this.inputElement.selectionStart = this.inputElement.value.length;
            this.inputElement.selectionEnd = this.inputElement.value.length;
        }, 0);
    }

    appendOutput(text, className = '') {
        try {
            if (!this.consoleElement) {
                throw new Error('Console output element not found');
            }

            const line = document.createElement('div');
            line.className = `console-line ${className}`;

            if (typeof text === 'object') {
                // Pretty print objects
                line.innerHTML = `<pre>${JSON.stringify(text, null, 2)}</pre>`;
            } else {
                // Handle ANSI color codes
                line.innerHTML = this.processAnsiCodes(String(text));
            }

            this.consoleElement.appendChild(line);
            this.consoleElement.scrollTop = this.consoleElement.scrollHeight;

            // Manage buffer size
            this.outputBuffer.push({ text, className });
            if (this.outputBuffer.length > this.maxBufferSize) {
                this.outputBuffer.shift();
                // Remove oldest line from DOM
                if (this.consoleElement.firstChild) {
                    this.consoleElement.removeChild(this.consoleElement.firstChild);
                }
            }
        } catch (error) {
            console.error('Error appending output:', error);
        }
    }

    processAnsiCodes(text) {
        // Convert ANSI color codes to CSS classes
        return text
            .replace(/\x1b\[31m/g, '<span class="ansi-red">')
            .replace(/\x1b\[32m/g, '<span class="ansi-green">')
            .replace(/\x1b\[33m/g, '<span class="ansi-yellow">')
            .replace(/\x1b\[0m/g, '</span>')
            .replace(/\n/g, '<br>');
    }

    handleInput(input) {
        if (!this.isEnabled) return;

        try {
            // Add to history if not empty and different from last entry
            if (input && (!this.inputHistory.length || this.inputHistory[this.inputHistory.length - 1] !== input)) {
                this.inputHistory.push(input);
                if (this.inputHistory.length > 50) { // Limit history size
                    this.inputHistory.shift();
                }
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

            // Emit input event for program to handle
            this.emitInput(input);

        } catch (error) {
            console.error('Error handling input:', error);
            this.setError('Failed to process input');
        }
    }

    emitInput(input) {
        // Create and dispatch a custom event
        const event = new CustomEvent('console-input', {
            detail: { input: input }
        });
        document.dispatchEvent(event);
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
            this.inputElement.placeholder = "Type your input here...";
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