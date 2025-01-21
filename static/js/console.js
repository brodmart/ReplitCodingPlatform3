/**
 * Interactive Console class for handling real-time program I/O using Xterm.js
 */
class InteractiveConsole {
    constructor() {
        console.log('Initializing InteractiveConsole');
        this.terminal = null;
        this.fitAddon = null;
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.isSessionValid = false;
        this.isInitialized = false;
        this.isBusy = false;
        this.pollTimer = null;
        this.polling = false;
        this.pollRetryCount = 0;
        this.maxRetries = 5;
        this.currentPollInterval = 100;
        this.inputBuffer = '';
        this.inputCallback = null;

        // Get CSRF token
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        this.csrfToken = metaToken ? metaToken.content : null;

        if (!this.csrfToken) {
            console.error('CSRF token not found');
            throw new Error('CSRF token not found');
        }
    }

    async init() {
        try {
            console.log('Starting console initialization');
            const terminalContainer = document.getElementById('terminal-container');

            if (!terminalContainer) {
                throw new Error('Terminal container not found');
            }

            // Initialize Xterm.js
            this.terminal = new Terminal({
                cursorBlink: true,
                fontSize: 14,
                fontFamily: 'Consolas, "Liberation Mono", Menlo, Courier, monospace',
                theme: {
                    background: '#1e1e1e',
                    foreground: '#d4d4d4'
                },
                scrollback: 1000,
                convertEol: true
            });

            // Initialize FitAddon
            this.fitAddon = new FitAddon.FitAddon();
            this.terminal.loadAddon(this.fitAddon);

            // Open terminal
            this.terminal.open(terminalContainer);
            this.fitAddon.fit();

            // Handle terminal input
            this.terminal.onData(data => {
                if (this.isWaitingForInput) {
                    if (data === '\r') { // Enter key
                        this.terminal.write('\r\n');
                        const input = this.inputBuffer;
                        this.inputBuffer = '';
                        if (this.inputCallback) {
                            this.inputCallback(input);
                        }
                    } else if (data === '\u007f') { // Backspace
                        if (this.inputBuffer.length > 0) {
                            this.inputBuffer = this.inputBuffer.slice(0, -1);
                            this.terminal.write('\b \b');
                        }
                    } else {
                        this.inputBuffer += data;
                        this.terminal.write(data);
                    }
                }
            });

            // Handle window resize
            window.addEventListener('resize', () => {
                this.fitAddon.fit();
            });

            this.isInitialized = true;
            console.log('Console initialization successful');
            return true;
        } catch (error) {
            console.error('Failed to initialize console:', error);
            this.isInitialized = false;
            throw error;
        }
    }

    async executeCode(code, language) {
        if (!this.isInitialized) {
            throw new Error('Console not initialized');
        }

        if (!code?.trim()) {
            throw new Error('No code to execute');
        }

        if (this.isBusy) {
            throw new Error('Console is busy');
        }

        this.isBusy = true;

        try {
            await this.cleanupConsole();
            this.terminal.clear();
            this.terminal.write('Starting compilation...\r\n');

            const success = await this.startSession(code, language);
            if (!success) {
                throw new Error('Failed to start program execution');
            }

            await this.startPolling();
            return true;
        } catch (error) {
            console.error('Error executing code:', error);
            this.terminal.write(`\r\nError: ${error.message}\r\n`);
            throw error;
        } finally {
            this.isBusy = false;
        }
    }

    async cleanupConsole() {
        try {
            if (this.pollTimer) {
                clearTimeout(this.pollTimer);
                this.pollTimer = null;
            }

            if (this.sessionId) {
                await this.endSession();
            }

            this.terminal.clear();
            this.sessionId = null;
            this.isWaitingForInput = false;
            this.isSessionValid = false;
            this.pollRetryCount = 0;
            this.polling = false;
            this.inputBuffer = '';
            return true;
        } catch (error) {
            console.error('Error in cleanupConsole:', error);
            return false;
        }
    }

    async startSession(code, language) {
        if (!this.isInitialized) {
            throw new Error('Console not initialized');
        }

        this.terminal.write('Starting compilation...\r\n');
        if (code.length > 50000) {
            this.terminal.write('Large code submission detected, this may take longer...\r\n');
        }

        console.log('Starting new session with:', { language, codeLength: code.length });

        try {
            const response = await fetch('/activities/start_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                credentials: 'same-origin',
                body: JSON.stringify({ code, language })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Session start response:', data);

            if (!data.success) {
                throw new Error(data.error || 'Failed to start session');
            }

            this.terminal.write('Compilation successful\r\n');
            if (data.compilation_time) {
                this.terminal.write(`Compiled in ${data.compilation_time.toFixed(2)}s\r\n`);
            }

            this.sessionId = data.session_id;
            this.isSessionValid = true;
            this.pollRetryCount = 0;
            return true;
        } catch (error) {
            console.error('Error in startSession:', error);
            this.terminal.write(`Error: ${error.message}\r\n`);
            return false;
        }
    }

    async startPolling() {
        if (!this.sessionId || !this.isSessionValid) {
            console.log('Cannot start polling: invalid session');
            return;
        }

        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
            this.pollTimer = null;
        }

        this.currentPollInterval = this.baseDelay;
        this.pollRetryCount = 0;
        console.log('Starting polling for session:', this.sessionId);
        await this.poll();
    }

    async sendInput(input) {
        if (!this.sessionId || !this.isSessionValid) {
            console.error('Cannot send input: invalid session');
            return;
        }

        try {
            console.log('Sending input:', input);
            const response = await fetch('/activities/send_input', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    session_id: this.sessionId,
                    input
                })
            });

            const data = await response.json();
            if (!data.success) {
                throw new Error(data.error || 'Failed to send input');
            }

            this.inputElement.value = '';
            this.inputElement.focus();
            this.currentPollInterval = this.baseDelay;
            await this.poll(); 
        } catch (error) {
            console.error('Error sending input:', error);
            this.terminal.write('Error: Failed to send input\r\n');
        }
    }

    async poll() {
        if (!this.sessionId || !this.isSessionValid) {
            console.log('Poll skipped - invalid session');
            return;
        }

        if (this.polling) {
            console.log('Poll skipped - already polling');
            return;
        }

        this.polling = true;
        console.log('Polling for output...');

        try {
            const url = `/activities/get_output?session_id=${this.sessionId}`;
            console.log('Making GET request to:', url);

            const response = await fetch(url, {
                credentials: 'same-origin',
                headers: {
                    'X-CSRF-Token': this.csrfToken,
                    'Accept': 'application/json'
                }
            });

            if (!response.ok) {
                console.error('Poll response not OK:', response.status, response.statusText);
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Poll response data:', data);

            if (!data.success) {
                throw new Error(data.error || 'Failed to get output');
            }

            if (data.output) {
                console.log('Received output:', data.output);
                this.appendToConsole(data.output);
                this.currentPollInterval = this.baseDelay;

                if (data.output.includes('Enter') || 
                    data.output.includes('Input') ||
                    data.output.includes('Entrez') ||
                    data.output.includes('Saisissez') ||
                    data.output.toLowerCase().includes('choix')) {
                    data.waiting_for_input = true;
                }
            } 

            if (data.session_ended) {
                console.log('Session ended');
                this.isSessionValid = false;
                this.setInputState(false);
                return;
            }

            if (data.waiting_for_input !== this.isWaitingForInput) {
                console.log('Input state change requested:', data.waiting_for_input);

                if (data.waiting_for_input) {
                    this.setInputState(true);
                } else {
                    this.setInputState(false);
                }
            }

            const nextPollDelay = this.calculateNextPollDelay(data);

            if (this.isSessionValid) {
                console.log(`Scheduling next poll with interval: ${nextPollDelay}ms`);
                this.pollTimer = setTimeout(() => this.poll(), nextPollDelay);
            }

        } catch (error) {
            console.error('Poll error:', error);
            this.handlePollError(error);
        } finally {
            this.polling = false;
        }
    }

    calculateNextPollDelay(data) {
        if (this.isWaitingForInput) {
            return 2000; 
        }

        return this.baseDelay; 
    }

    handlePollError(error) {
        this.pollRetryCount++;
        console.error(`Poll error (attempt ${this.pollRetryCount}/${this.maxRetries}):`, error);

        if (this.pollRetryCount >= this.maxRetries) {
            this.isSessionValid = false;
            this.terminal.write(`Error: Maximum polling retries reached. Please try again.\r\n`);
            if (this.pollTimer) {
                clearTimeout(this.pollTimer);
                this.pollTimer = null;
            }
            return;
        }

        this.currentPollInterval = Math.min(
            this.currentPollInterval * 1.5,
            2000
        );

        console.log(`Retrying poll in ${this.currentPollInterval}ms`);
        this.pollTimer = setTimeout(() => this.poll(), this.currentPollInterval);
    }

    appendToConsole(text, type = 'output') {
        if (!text || !this.terminal) {
            return;
        }

        // Handle ANSI color codes based on message type
        const colors = {
            error: '\x1b[31m', // Red
            info: '\x1b[36m',  // Cyan
            input: '\x1b[34m', // Blue
            output: '\x1b[0m'  // Default
        };

        const resetColor = '\x1b[0m';
        const color = colors[type] || colors.output;

        // Write to terminal with proper color and line endings
        this.terminal.write(`${color}${text}${resetColor}`);

        // Ensure proper line ending
        if (!text.endsWith('\n')) {
            this.terminal.write('\r\n');
        }
    }

    setupEventListeners() {
        // This method is largely irrelevant now that input is handled by Xterm.js
    }


    setInputState(enabled) {
        if (!this.terminal) {
            console.error('Terminal not found');
            return;
        }

        console.log('Setting input state:', enabled);

        this.isWaitingForInput = enabled;
        if (enabled){
            this.inputCallback = input => this.sendInput(input);
        } else {
            this.inputCallback = null;
        }

    }

    async endSession() {
        if (!this.sessionId || !this.isSessionValid) {
            return;
        }

        try {
            const response = await fetch('/activities/end_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                credentials: 'same-origin',
                body: JSON.stringify({ session_id: this.sessionId })
            });

            if (!response.ok) {
                console.warn('Failed to end session:', response.status);
            }
        } catch (error) {
            console.error('Error ending session:', error);
        } finally {
            this.sessionId = null;
            this.isSessionValid = false;
        }
    }
}

// Export to window
window.InteractiveConsole = InteractiveConsole;