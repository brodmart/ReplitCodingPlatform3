/**
 * Enhanced Interactive Console class for handling real-time program I/O
 * Similar to W3Schools/CodePen implementation
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.outputElement = options.outputElement;
        this.inputElement = options.inputElement;
        this.onCommand = options.onCommand;
        this.onInput = options.onInput;
        this.onClear = options.onClear;

        if (!this.outputElement || !this.inputElement) {
            throw new Error('Console requires output and input elements');
        }

        this.history = [];
        this.historyIndex = -1;
        this.inputBuffer = '';
        this.isWaitingForInput = false;
        this.maxBufferSize = 1000;
        this.outputBuffer = [];

        this.setupEventListeners();
        this.clear();
        this.enable();
    }

    setupEventListeners() {
        this.inputElement.addEventListener('keydown', (e) => {
            if (!this.isEnabled) return;

            switch(e.key) {
                case 'Enter':
                    if (!e.shiftKey) {
                        e.preventDefault();
                        this.handleEnterKey();
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
                case 'c':
                    if (e.ctrlKey) {
                        this.handleCtrlC();
                    }
                    break;
                case 'l':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        this.clear();
                    }
                    break;

            }
        });
    }

    handleEnterKey() {
        const input = this.inputElement.value.trim();

        if (this.isWaitingForInput) {
            this.appendOutput(`${input}\n`);
            if (this.onInput) {
                this.onInput(input);
            }
        } else if (input) {
            this.history.push(input);
            this.historyIndex = this.history.length;
            this.appendOutput(`> ${input}\n`);

            if (this.onCommand) {
                this.onCommand(input);
            }
        }

        this.inputElement.value = '';
    }

    navigateHistory(direction) {
        if (!this.history.length) return;

        this.historyIndex += direction;

        if (this.historyIndex >= this.history.length) {
            this.historyIndex = this.history.length - 1;
        } else if (this.historyIndex < 0) {
            this.historyIndex = 0;
        }

        this.inputElement.value = this.history[this.historyIndex];
        // Move cursor to end of input
        setTimeout(() => {
            this.inputElement.selectionStart = this.inputElement.value.length;
            this.inputElement.selectionEnd = this.inputElement.value.length;
        }, 0);
    }

    handleTabCompletion() {
        // Implement code completion here
        // This will be similar to W3Schools' implementation
    }

    handleCtrlC() {
        if (this.isWaitingForInput) {
            this.appendOutput('^C\n');
            this.isWaitingForInput = false;
            this.enable();
        }
    }

    appendOutput(text, className = '') {
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
    }

    processAnsiCodes(text) {
        const ansiColorMap = {
            '31': 'console-error',
            '32': 'console-success',
            '33': 'console-warning',
            '34': 'console-info',
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
                const classes = p1.split(';')
                    .map(code => ansiColorMap[code])
                    .filter(Boolean)
                    .join(' ');
                return classes ? `<span class="${classes}">` : '</span>';
            })
            .replace(/\n/g, '<br>');
    }

    appendError(message) {
        this.appendOutput(message, 'console-error');
    }

    appendSuccess(message) {
        this.appendOutput(message, 'console-success');
    }

    clear() {
        if (this.outputElement) {
            this.outputElement.innerHTML = '';
            this.outputBuffer = [];
            if (this.onClear) {
                this.onClear();
            }
        }
    }

    enable() {
        if (this.inputElement) {
            this.isEnabled = true;
            this.inputElement.disabled = false;
            this.inputElement.focus();
        }
    }

    disable() {
        if (this.inputElement) {
            this.isEnabled = false;
            this.inputElement.disabled = true;
        }
    }

    waitForInput(prompt = '') {
        this.isWaitingForInput = true;
        this.appendOutput(prompt);
        this.inputElement.focus();
        return new Promise(resolve => {
            this.onInput = (input) => {
                this.isWaitingForInput = false;
                resolve(input);
            };
        });
    }
}

// Export to window object
try {
    window.InteractiveConsole = InteractiveConsole;
} catch (error) {
    console.error('Failed to export InteractiveConsole:', error);
}