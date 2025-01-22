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
        this.inputPromptPatterns = {
            cpp: ['>', '>>'],
            python: ['>>>', '...']
        };
    }

    setupSocketHandlers() {
        this.socket.on('connect', () => {
            console.debug('Socket.IO connected');
            this.appendSystemMessage('Console connected');
        });

        this.socket.on('disconnect', () => {
            console.debug('Socket.IO disconnected');
            this.appendSystemMessage('Console disconnected. Attempting to reconnect...');
        });

        this.socket.on('error', (error) => {
            console.error('Socket.IO error:', error);
            this.appendError(`Error: ${error.message}`);
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
                this.appendOutput(data.output);
                this.isWaitingForInput = data.waiting_for_input || false;
                if (this.isWaitingForInput) {
                    this.enableInput();
                } else {
                    this.disableInput();
                }
            }
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
                    if (!this.isWaitingForInput) {
                        e.preventDefault();
                        this.navigateHistory(-1);
                    }
                    break;
                case 'ArrowDown':
                    if (!this.isWaitingForInput) {
                        e.preventDefault();
                        this.navigateHistory(1);
                    }
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
        const input = this.inputElement.value.trim();
        this.inputElement.value = '';

        if (this.sessionId && this.isWaitingForInput) {
            if (this.socket && this.socket.connected) {
                this.socket.emit('input', {
                    session_id: this.sessionId,
                    input: input + '\n'
                });
                this.appendOutput(input + '\n', 'user-input');
                this.isWaitingForInput = false;
                this.disableInput();
                return;
            } else {
                this.appendError('Not connected to server. Reconnecting...');
                this.socket.connect();
            }
        } else if (input) {
            this.history.push(input);
            this.historyIndex = this.history.length;
            this.appendOutput(`> ${input}\n`, 'console-input');

            // Assuming onCommand remains for non-interactive commands.
            //if (this.onCommand) {
            //    await this.onCommand(input);
            //}
        }
    }

    async handleCtrlC() {
        if (this.sessionId) {
            if (this.socket && this.socket.connected) {
                this.socket.emit('interrupt');
                this.appendOutput('^C\n', 'console-input');
                this.handleSessionEnd(); // Handle session end through Socket.IO
            } else {
                this.appendError('Not connected to server, cannot interrupt');
            }
        }
    }

    appendOutput(text, className = 'console-output') {
        const processedText = this.processAnsiCodes(text);
        const lines = processedText.split('\n');
        for (const line of lines) {
            if (line.trim() || className.includes('user-input')) {
                const element = document.createElement('div');
                element.className = className;
                element.innerHTML = line; // Use innerHTML for ANSI codes
                this.outputElement.appendChild(element);
            }
        }
        this.outputElement.scrollTop = this.outputElement.scrollHeight;

        // Trim output buffer
        while (this.outputElement.children.length > this.maxBufferSize) {
            this.outputElement.removeChild(this.outputElement.firstChild);
        }
    }

    appendError(message) {
        this.appendOutput(message, 'console-error');
    }

    appendSystemMessage(message) {
        this.appendOutput(message, 'console-system');
    }

    clear() {
        this.outputElement.innerHTML = '';
        this.isWaitingForInput = false;
        this.sessionId = null;
        this.history = [];
        this.historyIndex = -1;
    }

    enableInput() {
        this.isEnabled = true;
        this.inputElement.disabled = false;
        this.inputElement.focus();
    }

    disableInput() {
        this.isEnabled = false;
        this.inputElement.disabled = true;
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
        if (sessionId && this.socket && this.socket.connected) {
            this.socket.emit('session_start', {
                session_id: sessionId
            });
        }
    }

    handleSessionEnd() {
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.enableInput();
        this.appendOutput('\nSession ended.\n', 'console-info');
        if (this.socket) {
            this.socket.close();
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