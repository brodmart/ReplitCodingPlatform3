/**
 * Interactive Console class for handling real-time program I/O using CodeMirror
 */
class InteractiveConsole {
    constructor(options = {}) {
        if (!options.outputElement || !options.inputElement) {
            throw new Error('Console requires output and input elements');
        }

        this.outputElement = options.outputElement;
        this.inputElement = options.inputElement;
        this.onCommand = options.onCommand;

        this.outputBuffer = [];
        this.inputHistory = [];
        this.historyIndex = -1;
        this.currentInput = '';
        this.isEnabled = true;
        this.isWaitingForInput = false;
        this.maxBufferSize = 1000;
        this.currentLanguage = 'cpp'; // Default language

        // Initialize console state
        this.clear();
        this.setupEventListeners();
        this.enable();
    }

    setupEventListeners() {
        try {
            if (!this.inputElement) {
                throw new Error('Input element not available for event setup');
            }

            // Input handling with improved keyboard shortcuts
            this.inputElement.addEventListener('keydown', (e) => {
                if (!this.isEnabled) return;

                switch(e.key) {
                    case 'Enter':
                        if (!e.shiftKey) {
                            e.preventDefault();
                            const input = this.inputElement.value.trim();
                            if (input) {
                                this.handleInput(input);
                            }
                        }
                        break;
                    case 'ArrowUp':
                        e.preventDefault();
                        this.navigateHistory(-1);
                        break;
                    case 'ArrowDown':
                        e.preventDefault();
                        this.navigateHistory(1);
                        break;
                    case 'Tab':
                        e.preventDefault();
                        this.handleTabCompletion();
                        break;
                    case 'l':
                        if (e.ctrlKey) {
                            e.preventDefault();
                            this.clear();
                        }
                        break;
                    case 'c':
                        if (e.ctrlKey) {
                            if (this.isWaitingForInput) {
                                this.handleInterrupt();
                            } else {
                                // Copy selected text
                                const selection = window.getSelection().toString();
                                if (selection) {
                                    navigator.clipboard.writeText(selection);
                                }
                            }
                        }
                        break;
                }
            });

            // Handle paste events with smart formatting
            this.inputElement.addEventListener('paste', (e) => {
                e.preventDefault();
                const text = e.clipboardData.getData('text');
                this.handlePaste(text);
            });

            // Language change handler
            document.getElementById('languageSelect')?.addEventListener('change', (e) => {
                this.currentLanguage = e.target.value;
                this.clear();
                this.appendOutput(`Switched to ${this.currentLanguage} mode`, 'info');
            });

        } catch (error) {
            console.error('Error in console event setup:', error);
            throw error;
        }
    }

    handlePaste(text) {
        const lines = text.split('\n');
        if (lines.length > 1) {
            // If multi-line, prompt for confirmation
            if (confirm('Paste multiple lines?')) {
                lines.forEach((line, index) => {
                    setTimeout(() => {
                        this.inputElement.value = line.trim();
                        this.handleInput(line.trim());
                    }, index * 100);
                });
            }
        } else {
            this.inputElement.value = text;
        }
    }

    handleTabCompletion() {
        const input = this.inputElement.value;
        const words = input.split(/\s+/);
        const lastWord = words[words.length - 1];

        // Language-specific completions
        const completions = {
            cpp: ['cout', 'cin', 'endl', 'include', 'using', 'namespace', 'std', 'int', 'float', 'double', 'char'],
            csharp: ['Console', 'Write', 'WriteLine', 'ReadLine', 'using', 'System', 'string', 'int', 'bool', 'var']
        };

        const suggestions = (completions[this.currentLanguage] || [])
            .filter(word => word.toLowerCase().startsWith(lastWord.toLowerCase()));

        if (suggestions.length === 1) {
            words[words.length - 1] = suggestions[0];
            this.inputElement.value = words.join(' ');
        } else if (suggestions.length > 1) {
            this.appendOutput('\nSuggestions:', 'info');
            suggestions.forEach(s => this.appendOutput(s));
            this.appendOutput('');
        }
    }

    handleInterrupt() {
        this.appendOutput('^C', 'interrupt');
        this.isWaitingForInput = false;
        this.enable();
        if (this.onCommand) {
            this.onCommand('interrupt');
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

        // Move cursor to end of input
        setTimeout(() => {
            this.inputElement.selectionStart = this.inputElement.value.length;
            this.inputElement.selectionEnd = this.inputElement.value.length;
        }, 0);
    }

    appendOutput(text, className = '') {
        try {
            if (!this.outputElement) {
                throw new Error('Console output element not found');
            }

            const line = document.createElement('div');
            line.className = `console-line ${className}`;

            if (typeof text === 'object') {
                line.innerHTML = `<pre>${JSON.stringify(text, null, 2)}</pre>`;
            } else {
                line.innerHTML = this.processAnsiCodes(String(text));
            }

            this.outputElement.appendChild(line);
            this.outputElement.scrollTop = this.outputElement.scrollHeight;

            // Manage buffer size
            this.outputBuffer.push({ text, className });
            if (this.outputBuffer.length > this.maxBufferSize) {
                this.outputBuffer.shift();
                if (this.outputElement.firstChild) {
                    this.outputElement.removeChild(this.outputElement.firstChild);
                }
            }
        } catch (error) {
            console.error('Error appending output:', error);
        }
    }

    processAnsiCodes(text) {
        // Enhanced ANSI color code support
        return text
            .replace(/\x1b\[31m/g, '<span class="ansi-red">')    // Error
            .replace(/\x1b\[32m/g, '<span class="ansi-green">')  // Success
            .replace(/\x1b\[33m/g, '<span class="ansi-yellow">') // Warning
            .replace(/\x1b\[34m/g, '<span class="ansi-blue">')   // Info
            .replace(/\x1b\[35m/g, '<span class="ansi-magenta">')
            .replace(/\x1b\[36m/g, '<span class="ansi-cyan">')
            .replace(/\x1b\[37m/g, '<span class="ansi-white">')
            .replace(/\x1b\[1m/g, '<span class="ansi-bold">')
            .replace(/\x1b\[3m/g, '<span class="ansi-italic">')
            .replace(/\x1b\[0m/g, '</span>')
            .replace(/\n/g, '<br>');
    }

    handleInput(input) {
        if (!this.isEnabled) return;

        try {
            // Add to history if not empty and different from last entry
            if (input && (!this.inputHistory.length || this.inputHistory[this.inputHistory.length - 1] !== input)) {
                this.inputHistory.push(input);
                if (this.inputHistory.length > 50) {
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

            // Execute command through callback
            if (this.onCommand) {
                this.onCommand(input);
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
            if (!this.outputElement) {
                throw new Error('Console element not found');
            }
            this.outputElement.innerHTML = '';
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
            this.inputElement.placeholder = "Type your command here...";
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

// Export to window object and handle initialization errors
try {
    window.InteractiveConsole = InteractiveConsole;
} catch (error) {
    console.error('Failed to export InteractiveConsole:', error);
}