/**
 * Enhanced Interactive Console class for handling real-time program I/O using CodeMirror
 * Similar to W3Schools/CodePen implementation
 */
class InteractiveConsole {
    constructor(options = {}) {
        if (!options.outputElement || !options.inputElement) {
            throw new Error('Console requires output and input elements');
        }

        this.outputElement = options.outputElement;
        this.inputElement = options.inputElement;
        this.onCommand = options.onCommand;
        this.onInput = options.onInput;
        this.onClear = options.onClear;

        this.outputBuffer = [];
        this.inputHistory = [];
        this.historyIndex = -1;
        this.currentInput = '';
        this.isEnabled = true;
        this.isWaitingForInput = false;
        this.maxBufferSize = 1000;
        this.currentLanguage = 'cpp';
        this.inputQueue = [];
        this.inputResolver = null;

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

            // Enhanced input handling with improved keyboard shortcuts
            this.inputElement.addEventListener('keydown', (e) => {
                if (!this.isEnabled) return;

                switch(e.key) {
                    case 'Enter':
                        if (!e.shiftKey) {
                            e.preventDefault();
                            const input = this.inputElement.value.trim();
                            if (this.isWaitingForInput) {
                                this.resolveInput(input);
                            } else if (input) {
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
                                const selection = window.getSelection().toString();
                                if (selection) {
                                    navigator.clipboard.writeText(selection);
                                }
                            }
                        }
                        break;
                }
            });

            // Language change handler with improved state management
            document.getElementById('languageSelect')?.addEventListener('change', (e) => {
                this.currentLanguage = e.target.value;
                this.clear();
                this.appendOutput(`Switched to ${this.currentLanguage} mode`, 'info');
                localStorage.setItem('selectedLanguage', this.currentLanguage);
            });

        } catch (error) {
            console.error('Error in console event setup:', error);
            throw error;
        }
    }

    // Enhanced input handling for program interaction
    async waitForInput(prompt = '') {
        return new Promise((resolve) => {
            this.isWaitingForInput = true;
            this.inputResolver = resolve;
            this.appendOutput(prompt, 'input-prompt');
            this.inputElement.focus();
            this.inputElement.placeholder = 'Type your input here...';
        });
    }

    resolveInput(input) {
        if (this.inputResolver) {
            this.appendOutput(input, 'user-input');
            this.inputResolver(input);
            this.inputResolver = null;
            this.isWaitingForInput = false;
            this.inputElement.value = '';
            this.inputElement.placeholder = 'Press Enter to send';
        }
    }

    handleInput(input) {
        if (!this.isEnabled) return;

        try {
            if (input && (!this.inputHistory.length || this.inputHistory[this.inputHistory.length - 1] !== input)) {
                this.inputHistory.push(input);
                if (this.inputHistory.length > 50) {
                    this.inputHistory.shift();
                }
            }

            this.historyIndex = -1;
            this.appendOutput(`> ${input}`, 'input');
            this.inputElement.value = '';

            if (input.toLowerCase() === 'clear') {
                this.clear();
                return;
            }

            if (this.onCommand) {
                this.onCommand(input);
            }

        } catch (error) {
            console.error('Error handling input:', error);
            this.appendError('Failed to process input');
        }
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

    appendError(message) {
        this.appendOutput(message, 'error');
    }

    appendSuccess(message) {
        this.appendOutput(message, 'success');
    }

    clear() {
        try {
            if (!this.outputElement) {
                throw new Error('Console element not found');
            }
            this.outputElement.innerHTML = '';
            this.outputBuffer = [];
            if (this.onClear) {
                this.onClear();
            }
        } catch (error) {
            console.error('Error clearing console:', error);
        }
    }

    processAnsiCodes(text) {
        const ansiColorMap = {
            '30': 'ansi-black',
            '31': 'ansi-red',
            '32': 'ansi-green',
            '33': 'ansi-yellow',
            '34': 'ansi-blue',
            '35': 'ansi-magenta',
            '36': 'ansi-cyan',
            '37': 'ansi-white',
            '1': 'ansi-bold',
            '3': 'ansi-italic'
        };

        return text
            .replace(/\x1b\[([0-9;]*)m/g, (match, p1) => {
                const codes = p1.split(';');
                const classes = codes
                    .map(code => ansiColorMap[code])
                    .filter(Boolean)
                    .join(' ');
                return classes ? `<span class="${classes}">` : '</span>';
            })
            .replace(/\n/g, '<br>');
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