/**
 * Enhanced Interactive Console class for handling real-time program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.outputElement = options.outputElement;
        this.inputElement = options.inputElement;
        this.language = options.language || 'cpp';
        this.isWaitingForInput = false;
        this.sessionId = null;

        if (!this.outputElement || !this.inputElement) {
            throw new Error('Console requires output and input elements');
        }

        this.socket = io({
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000,
            timeout: 20000
        });

        this.setupSocketHandlers();
        this.setupInputHandlers();
        this.clear();
        this.history = [];
        this.historyIndex = -1;
        this.maxBufferSize = 4096;
        this.inputBuffer = '';
    }

    setupSocketHandlers() {
        this.socket.on('connect', () => {
            console.debug('Socket.IO connected');
            this.appendSystemMessage('Console connected');
        });

        this.socket.on('disconnect', () => {
            console.debug('Socket.IO disconnected');
            this.appendSystemMessage('Console disconnected. Attempting to reconnect...');
            this.disableInput();
        });

        this.socket.on('error', (error) => {
            console.error('Socket.IO error:', error);
            this.appendError(`Error: ${error.message}`);
            this.disableInput();
        });

        this.socket.on('compilation_result', (result) => {
            console.debug('Compilation result:', result);
            if (result.success) {
                this.sessionId = result.session_id;
                if (!result.interactive && result.output) {
                    this.appendOutput(result.output);
                }
            } else {
                this.appendError(`Compilation Error: ${result.error}`);
            }
        });

        this.socket.on('output', (data) => {
            console.debug('Received output:', data);
            if (data.output) {
                // Clean and process the output
                const processedOutput = this.processAnsiCodes(data.output.replace(/\r\n/g, '\n'));
                this.appendOutput(processedOutput);

                // Update waiting for input state
                this.isWaitingForInput = data.waiting_for_input || false;
                if (this.isWaitingForInput) {
                    this.enableInput();
                } else {
                    this.disableInput();
                }
            }

            if (data.error) {
                this.appendError(data.error);
                this.disableInput();
            }

            // Auto-scroll to bottom
            this.outputElement.scrollTop = this.outputElement.scrollHeight;
        });
    }

    setupInputHandlers() {
        this.inputElement.addEventListener('keydown', async (e) => {
            if (!this.isEnabled) return;

            switch (e.key) {
                case 'Enter':
                    if (!e.shiftKey) {
                        e.preventDefault();
                        await this.handleInput();
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
                case 'c':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        await this.handleCtrlC();
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

        // Handle paste events
        this.inputElement.addEventListener('paste', (e) => {
            if (!this.isEnabled) return;

            e.preventDefault();
            const text = e.clipboardData.getData('text');
            if (this.isWaitingForInput) {
                // For interactive input, only take the first line
                const firstLine = text.split('\n')[0];
                this.inputElement.value = firstLine;
                if (firstLine) {
                    this.handleInput();
                }
            } else {
                // For command input, can accept multiple lines
                this.inputElement.value = text;
            }
        });
    }

    async handleInput() {
        const input = this.inputElement.value;
        this.inputElement.value = '';

        if (!input) return;

        // Add input to history
        this.history.push(input);
        this.historyIndex = this.history.length;

        if (this.sessionId && this.isWaitingForInput) {
            if (this.socket && this.socket.connected) {
                // Append the input to our buffer
                this.inputBuffer += input;

                // Display the input with proper styling
                this.appendOutput(input + '\n', 'console-input');

                // Send the input with a newline
                this.socket.emit('input', {
                    session_id: this.sessionId,
                    input: input + '\n'
                });

                // Temporarily disable input until we get more output
                this.isWaitingForInput = false;
                this.disableInput();
            } else {
                this.appendError('Not connected to server. Reconnecting...');
                this.socket.connect();
            }
        } else {
            // For non-interactive mode, just show the input
            this.appendOutput(`> ${input}\n`, 'console-input');
        }
    }

    async handleCtrlC() {
        if (this.sessionId) {
            if (this.socket && this.socket.connected) {
                this.socket.emit('interrupt', { session_id: this.sessionId });
                this.appendOutput('^C\n', 'console-input');
                this.handleSessionEnd();
            } else {
                this.appendError('Not connected to server');
            }
        }
    }

    appendOutput(text, className = 'console-output') {
        const lines = text.split('\n');
        for (const line of lines) {
            if (line.trim() || className.includes('input')) {
                const element = document.createElement('div');
                element.className = `output-line ${className}`;
                element.innerHTML = line || '&nbsp;';  // Use &nbsp; for empty lines
                this.outputElement.appendChild(element);
            }
        }

        // Trim output buffer if needed
        while (this.outputElement.children.length > this.maxBufferSize) {
            this.outputElement.removeChild(this.outputElement.firstChild);
        }

        // Auto-scroll
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    appendError(message) {
        this.appendOutput(message, 'console-error');
    }

    appendSystemMessage(message) {
        this.appendOutput(message, 'console-system');
    }

    clear() {
        this.outputElement.innerHTML = '';
        this.inputBuffer = '';
        this.isWaitingForInput = false;
        this.sessionId = null;
    }

    enableInput() {
        this.isEnabled = true;
        this.inputElement.disabled = false;
        this.inputElement.placeholder = this.isWaitingForInput ? 'Enter input...' : 'Type a command...';
        this.inputElement.focus();
    }

    disableInput() {
        this.isEnabled = false;
        this.inputElement.disabled = true;
        this.inputElement.placeholder = 'Processing...';
    }

    setLanguage(language) {
        this.language = language;
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

    setSession(sessionId) {
        this.sessionId = sessionId;
        this.clear();
        if (sessionId && this.socket && this.socket.connected) {
            this.socket.emit('session_start', {
                session_id: sessionId
            });
        }
    }

    handleSessionEnd() {
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.inputBuffer = '';
        this.appendOutput('\nSession ended.\n', 'console-info');
        this.disableInput();
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
            '90': 'ansi-bright-black',
            '91': 'ansi-bright-red',
            '92': 'ansi-bright-green',
            '93': 'ansi-bright-yellow',
            '94': 'ansi-bright-blue',
            '95': 'ansi-bright-magenta',
            '96': 'ansi-bright-cyan',
            '97': 'ansi-bright-white',
            '1': 'ansi-bold',
            '3': 'ansi-italic',
            '4': 'ansi-underline'
        };

        return text
            .replace(/\x1b\[([0-9;]*)m/g, (match, p1) => {
                if (p1 === '0' || p1 === '') return '</span>';
                const classes = p1.split(';')
                    .map(code => ansiColorMap[code])
                    .filter(Boolean)
                    .join(' ');
                return classes ? `<span class="${classes}">` : '';
            });
    }
}

// Web Console I/O Handler
console.debug('Initializing web console...');

// Export to window object
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}