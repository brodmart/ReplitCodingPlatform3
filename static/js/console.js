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
        this.outputBuffer = '';
        this.inputBuffer = '';
        this.isProcessing = false;

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
    }

    setupSocketHandlers() {
        this.socket.on('connect', () => {
            console.debug('Socket.IO connected');
            this.appendSystemMessage('Console connected');
            if (this.sessionId) {
                this.socket.emit('session_start', { session_id: this.sessionId });
            }
        });

        this.socket.on('disconnect', () => {
            console.debug('Socket.IO disconnected');
            this.appendSystemMessage('Console disconnected. Attempting to reconnect...');
            this.disableInput();
        });

        this.socket.on('error', (error) => {
            console.error('Socket.IO error:', error);
            this.appendError(`Connection error: ${error.message}`);
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
                this.disableInput();
            }
        });

        // Enhanced output handling
        this.socket.on('output', (data) => {
            console.debug('Received output:', data);

            if (data.error) {
                this.appendError(data.error);
                this.disableInput();
                return;
            }

            if (data.output) {
                // Process and clean the output
                const cleanOutput = this.cleanOutput(data.output);
                this.outputBuffer += cleanOutput;

                // Process and display the output
                this.processAndDisplayOutput();

                // Update input state
                this.isWaitingForInput = data.waiting_for_input || false;
                this.updateInputState();
            }

            // Auto-scroll to bottom
            this.scrollToBottom();
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

            // For interactive input, only take the first line
            const firstLine = text.split('\n')[0];
            this.inputElement.value = firstLine;

            if (firstLine) {
                this.handleInput();
            }
        });
    }

    async handleInput() {
        if (!this.isEnabled || this.isProcessing) return;

        const input = this.inputElement.value;
        if (!input) return;

        this.inputElement.value = '';
        this.isProcessing = true;

        try {
            // Add to history
            if (!this.history.includes(input)) {
                this.history.push(input);
                this.historyIndex = this.history.length;
            }

            if (this.sessionId && this.isWaitingForInput) {
                if (this.socket && this.socket.connected) {
                    // Display the input
                    this.appendOutput(input + '\n', 'console-input');

                    // Send input to the server
                    this.socket.emit('input', {
                        session_id: this.sessionId,
                        input: input + '\n'
                    });

                    // Disable input until we get more output
                    this.isWaitingForInput = false;
                    this.disableInput();
                } else {
                    this.appendError('Not connected to server. Reconnecting...');
                    this.socket.connect();
                }
            } else {
                this.appendOutput(`> ${input}\n`, 'console-input');
            }
        } catch (error) {
            console.error('Input handling error:', error);
            this.appendError(`Failed to process input: ${error.message}`);
        } finally {
            this.isProcessing = false;
        }
    }

    cleanOutput(output) {
        return output.replace(/\r\n/g, '\n')
                    .replace(/\r/g, '\n');
    }

    processAndDisplayOutput() {
        const lines = this.outputBuffer.split('\n');

        // Process each line
        for (const line of lines) {
            if (line.trim() || line === '') {
                this.appendOutput(line + '\n');
            }
        }

        // Clear the buffer
        this.outputBuffer = '';
    }

    updateInputState() {
        if (this.isWaitingForInput) {
            this.enableInput();
            this.inputElement.focus();
        } else {
            this.disableInput();
        }
    }

    async handleCtrlC() {
        if (!this.sessionId) return;

        try {
            if (this.socket && this.socket.connected) {
                this.socket.emit('interrupt', { session_id: this.sessionId });
                this.appendOutput('^C\n', 'console-input');
                this.handleSessionEnd();
            } else {
                this.appendError('Not connected to server');
            }
        } catch (error) {
            console.error('Failed to handle Ctrl+C:', error);
            this.appendError(`Interrupt failed: ${error.message}`);
        }
    }

    appendOutput(text, className = 'console-output') {
        const processedText = this.processAnsiCodes(text);
        const lines = processedText.split('\n');

        for (const line of lines.slice(0, -1)) {  // Don't process the last empty line
            const element = document.createElement('div');
            element.className = `output-line ${className}`;
            element.innerHTML = line || '&nbsp;';  // Use &nbsp; for empty lines
            this.outputElement.appendChild(element);
        }

        // Trim output if needed
        while (this.outputElement.children.length > this.maxBufferSize) {
            this.outputElement.removeChild(this.outputElement.firstChild);
        }

        this.scrollToBottom();
    }

    appendError(message) {
        this.appendOutput(`Error: ${message}\n`, 'console-error');
    }

    appendSystemMessage(message) {
        this.appendOutput(`System: ${message}\n`, 'console-system');
    }

    clear() {
        this.outputElement.innerHTML = '';
        this.outputBuffer = '';
        this.inputBuffer = '';
        this.isWaitingForInput = false;
        this.sessionId = null;
        this.isProcessing = false;
    }

    enableInput() {
        this.isEnabled = true;
        this.inputElement.disabled = false;
        this.inputElement.placeholder = this.isWaitingForInput ? 'Enter input...' : 'Type a command...';
        this.inputElement.classList.remove('console-disabled');
    }

    disableInput() {
        this.isEnabled = false;
        this.inputElement.disabled = true;
        this.inputElement.placeholder = 'Processing...';
        this.inputElement.classList.add('console-disabled');
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
            this.socket.emit('session_start', { session_id: sessionId });
        }
    }

    handleSessionEnd() {
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.inputBuffer = '';
        this.outputBuffer = '';
        this.isProcessing = false;
        this.appendOutput('\nSession ended.\n', 'console-info');
        this.disableInput();
    }

    scrollToBottom() {
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

        return text.replace(/\x1b\[([0-9;]*)m/g, (match, p1) => {
            if (p1 === '0' || p1 === '') return '</span>';
            const classes = p1.split(';')
                .map(code => ansiColorMap[code])
                .filter(Boolean)
                .join(' ');
            return classes ? `<span class="${classes}">` : '';
        });
    }
}

// Initialize web console
console.debug('Initializing web console...');

// Export to window object
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}