/**
 * Enhanced Interactive Console class for handling real-time program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.outputElement = options.outputElement;
        this.inputElement = options.inputElement;
        this.onCommand = options.onCommand;
        this.onInput = options.onInput;
        this.onClear = options.onClear;
        this.language = options.language || 'cpp';

        if (!this.outputElement || !this.inputElement) {
            throw new Error('Console requires output and input elements');
        }

        this.history = [];
        this.historyIndex = -1;
        this.inputBuffer = '';
        this.isWaitingForInput = false;
        this.maxBufferSize = 4096;
        this.outputBuffer = [];
        this.sessionId = null;
        this.lastOutputTime = Date.now();
        this.duplicateThreshold = 100; // ms to consider output as duplicate
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.socket = null; // Socket.IO instance

        this.setupEventListeners();
        this.setupSocketIO();
        this.clear();
        this.enable();
    }

    setupEventListeners() {
        this.inputElement.addEventListener('keydown', async (e) => {
            if (!this.isEnabled) return;

            switch(e.key) {
                case 'Enter':
                    if (!e.shiftKey) {
                        e.preventDefault();
                        await this.handleEnterKey();
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
                    this.handleEnterKey();
                }
            } else {
                // For command input, can accept multiple lines
                this.inputElement.value = text;
            }
        });
    }

    setupSocketIO() {
        // Connect to Socket.IO endpoint with reconnection options
        this.socket = io({
            reconnection: true,
            reconnectionAttempts: this.maxReconnectAttempts,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            timeout: 20000,
            autoConnect: true
        });

        this.socket.on('connect', () => {
            console.debug('Socket.IO connection established');
            this.reconnectAttempts = 0;
            this.appendOutput('Console connected\n', 'console-info');

            // Register current session if exists
            if (this.sessionId) {
                this.socket.emit('session_start', {
                    session_id: this.sessionId
                });
            }
        });

        this.socket.on('output', (data) => {
            if (data.type === 'output') {
                this.processAndAppendOutput(data.output);
                this.isWaitingForInput = data.waiting_for_input || false;
                if (this.isWaitingForInput) {
                    this.enable();
                    this.inputElement.focus();
                }
            }
        });

        this.socket.on('error', (error) => {
            console.error('Socket.IO error:', error);
            this.appendError(`Connection error: ${error.message}`);
        });

        this.socket.on('disconnect', (reason) => {
            console.debug('Socket.IO disconnected:', reason);
            this.appendOutput('Console disconnected. Attempting to reconnect...\n', 'console-warning');

            if (reason === 'io server disconnect') {
                // Server disconnected explicitly
                this.socket.connect();
            }
        });

        this.socket.on('connect_error', (error) => {
            console.error('Socket.IO connection error:', error);
            this.reconnectAttempts++;

            if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                this.appendError('Failed to connect to server after multiple attempts');
            }
        });
    }

    async handleEnterKey() {
        const input = this.inputElement.value.trim();
        this.inputElement.value = '';

        if (this.sessionId && this.isWaitingForInput) {
            if (this.socket && this.socket.connected) {
                this.socket.emit('input', {
                    session_id: this.sessionId,
                    input: input + '\n'
                });
                this.appendOutput(input + '\n', 'console-input user-input');
                this.isWaitingForInput = false;
                return;
            } else {
                this.appendError('Not connected to server. Reconnecting...');
                this.socket.connect();
            }
        } else if (input) {
            this.history.push(input);
            this.historyIndex = this.history.length;
            this.appendOutput(`> ${input}\n`, 'console-input');

            if (this.onCommand) {
                await this.onCommand(input);
            }
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

    startPollingOutput() {
        //This function is removed as it is no longer needed with Socket.IO
    }

    processAndAppendOutput(text) {
        // Prevent duplicate output from rapid polling
        const now = Date.now();
        if (now - this.lastOutputTime < this.duplicateThreshold && 
            this.outputBuffer.length > 0 && 
            this.outputBuffer[this.outputBuffer.length - 1] === text) {
            return;
        }
        this.lastOutputTime = now;

        // Clean up and normalize output
        let cleanedText = text
            .replace(/\r\n/g, '\n')
            .replace(/\r/g, '\n')
            .replace(/\n+/g, '\n')
            .replace(/^\n+/, '')
            .trim();

        if (cleanedText) {
            // Check for input prompts in the text
            const patterns = this.inputPromptPatterns[this.language.toLowerCase()] || [];
            const lowerText = cleanedText.toLowerCase();

            const isInputPrompt = patterns.some(pattern => lowerText.includes(pattern));
            const className = isInputPrompt ? 'console-output input-prompt' : 'console-output';

            const lines = cleanedText.split('\n');
            for (const line of lines) {
                if (line.trim() || lines.length > 1) {
                    this.appendOutput(line + '\n', className);
                }
            }

            // If this looks like an input prompt, enable input
            if (isInputPrompt) {
                this.isWaitingForInput = true;
                this.enable();
                this.inputElement.focus();
            }
        }
    }

    appendOutput(text, className = '') {
        const processedText = this.processAnsiCodes(text);
        const lines = processedText.split(/(\n)/);

        for (const line of lines) {
            if (line === '\n') {
                this.outputElement.appendChild(document.createElement('br'));
            } else if (line.trim() || className) {
                const lineElement = document.createElement('div');
                lineElement.className = `console-line ${className}`;
                lineElement.innerHTML = line;
                this.outputElement.appendChild(lineElement);
            }
        }

        // Trim output buffer
        while (this.outputElement.children.length > this.maxBufferSize) {
            this.outputElement.removeChild(this.outputElement.firstChild);
        }

        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    appendError(errorMessage) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'console-error';
        errorDiv.textContent = errorMessage;
        this.outputElement.appendChild(errorDiv);
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
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
    setLanguage(language) {
        this.language = language;
    }
    handleSessionEnd() {
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.enable();
        this.appendOutput('\nSession ended.\n', 'console-info');
        if (this.socket) {
            this.socket.close();
        }
    }
}

// Web Console I/O Handler
console.debug('Initializing web console...');

// Export to window object
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}