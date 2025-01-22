/**
 * Enhanced Interactive Console class for handling real-time program I/O
 * Improved output formatting and error handling for web-based interaction
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
        this.maxBufferSize = 4096;
        this.outputBuffer = [];
        this.sessionId = null;
        this.pollInterval = null;
        this.lastOutputTime = Date.now();
        this.duplicateThreshold = 100; // ms to consider output as duplicate

        this.setupEventListeners();
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

        // Improved paste handling for multi-line input
        this.inputElement.addEventListener('paste', (e) => {
            if (this.isWaitingForInput) {
                e.preventDefault();
                const text = e.clipboardData.getData('text');
                const lines = text.split('\n');
                if (lines.length > 0) {
                    // Only take the first line for single-line input prompts
                    this.inputElement.value = lines[0];
                    this.handleEnterKey();
                }
            }
        });
    }

    async handleEnterKey() {
        const input = this.inputElement.value.trim();
        this.inputElement.value = '';

        if (this.sessionId && this.isWaitingForInput) {
            try {
                const response = await fetch('/send_input', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content
                    },
                    body: JSON.stringify({
                        session_id: this.sessionId,
                        input: input + '\n'
                    })
                });

                if (!response.ok) {
                    throw new Error('Failed to send input');
                }

                const data = await response.json();
                if (data.success) {
                    this.appendOutput(`${input}\n`, 'console-input');
                    this.isWaitingForInput = false;
                } else {
                    this.appendError(`Error: ${data.error}`);
                }
            } catch (error) {
                this.appendError(`Error sending input: ${error.message}`);
            }
        } else if (input) {
            this.history.push(input);
            this.historyIndex = this.history.length;
            this.appendOutput(`> ${input}\n`);

            if (this.onCommand) {
                await this.onCommand(input);
            }
        }
    }

    startPollingOutput() {
        if (!this.sessionId) return;

        const pollOutput = async () => {
            if (!this.sessionId) return;

            try {
                const response = await fetch(`/get_output?session_id=${this.sessionId}`);
                if (!response.ok) {
                    throw new Error('Failed to get output');
                }

                const data = await response.json();
                if (data.success) {
                    if (data.output) {
                        this.processAndAppendOutput(data.output);
                    }

                    if (data.waiting_for_input !== this.isWaitingForInput) {
                        this.isWaitingForInput = data.waiting_for_input;
                        if (this.isWaitingForInput) {
                            this.enable();
                            this.inputElement.focus();
                        }
                    }

                    if (data.session_ended) {
                        this.sessionId = null;
                        this.isWaitingForInput = false;
                        clearInterval(this.pollInterval);
                        return;
                    }
                }
            } catch (error) {
                console.error('Error polling output:', error);
                this.appendError('Connection error: Failed to get console output');
            }

            // Continue polling if session is active
            if (this.sessionId) {
                this.pollInterval = setTimeout(pollOutput, 100);
            }
        };

        // Start polling
        pollOutput();
    }

    processAndAppendOutput(text) {
        // Prevent duplicate output that might come from rapid polling
        const now = Date.now();
        if (now - this.lastOutputTime < this.duplicateThreshold && 
            this.outputBuffer.length > 0 && 
            this.outputBuffer[this.outputBuffer.length - 1] === text) {
            return;
        }
        this.lastOutputTime = now;

        // Clean up common console artifacts
        let cleanedText = text
            .replace(/\r\n/g, '\n')  // Normalize line endings
            .replace(/\r/g, '\n')    // Replace any remaining \r with \n
            .replace(/\n+/g, '\n')   // Remove multiple consecutive newlines
            .replace(/^\n+/, '')     // Remove leading newlines
            .trim();                 // Remove trailing whitespace

        if (cleanedText) {
            this.appendOutput(cleanedText + '\n');
        }
    }

    appendOutput(text, className = '') {
        const processedText = this.processAnsiCodes(String(text));

        // Split into lines while preserving empty lines
        const lines = processedText.split(/(\n)/);

        for (const line of lines) {
            if (line === '\n') {
                // Add empty line
                this.outputElement.appendChild(document.createElement('br'));
            } else if (line.trim()) {
                const lineElement = document.createElement('div');
                lineElement.className = `console-line ${className}`;
                lineElement.innerHTML = line;
                this.outputElement.appendChild(lineElement);
            }
        }

        // Trim output if it exceeds maxBufferSize
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
            })
            .replace(/\r\n|\r|\n/g, '<br>');
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

    handleCtrlC() {
        if (this.isWaitingForInput) {
            this.appendOutput('^C\n');
            this.isWaitingForInput = false;
            this.enable();
            // Send termination signal to backend
            if (this.sessionId) {
                fetch('/terminate_session', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content
                    },
                    body: JSON.stringify({
                        session_id: this.sessionId
                    })
                }).catch(console.error);
            }
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
        if (sessionId) {
            this.startPollingOutput();
        }
    }
}

// Export to window object
try {
    window.InteractiveConsole = InteractiveConsole;
} catch (error) {
    console.error('Failed to export InteractiveConsole:', error);
}