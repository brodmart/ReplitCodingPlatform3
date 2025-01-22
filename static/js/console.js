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

        // Add paste event handler for better input handling
        this.inputElement.addEventListener('paste', (e) => {
            if (this.isWaitingForInput) {
                e.preventDefault();
                const text = e.clipboardData.getData('text');
                const lines = text.split('\n');
                if (lines.length > 0) {
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
                        input: input + '\n'  // Add newline for proper input handling
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
                        this.appendOutput(data.output);
                    }

                    // Update input state based on server response
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
            }

            // Continue polling if session is active
            if (this.sessionId) {
                this.pollInterval = setTimeout(pollOutput, 100);
            }
        };

        // Start polling
        pollOutput();
    }

    appendOutput(text, className = '') {
        const processedText = this.processAnsiCodes(String(text));
        const lines = processedText.split('\n');

        for (const line of lines) {
            if (line.trim()) {
                const lineElement = document.createElement('div');
                lineElement.className = `console-line ${className}`;
                lineElement.innerHTML = line;
                this.outputElement.appendChild(lineElement);
            }
        }

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