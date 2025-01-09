/**
 * Interactive Console class for handling real-time program I/O
 */
class InteractiveConsole {
    constructor() {
        this.outputElement = null;
        this.inputElement = null;
        this.inputLine = null;
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.isSessionValid = false;
        this.isInitialized = false;
        this.isBusy = false;
        this.pollTimer = null;
        this.polling = false;
        this.pollRetryCount = 0;
        this.maxRetries = 3;
        this.baseDelay = 100;

        // Get CSRF token
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        this.csrfToken = metaToken ? metaToken.content : null;

        if (!this.csrfToken) {
            throw new Error('CSRF token not found');
        }
    }

    async init() {
        try {
            console.log('Starting console initialization');
            await this.findElements();
            this.setupEventListeners();
            await this.cleanupConsole();
            this.isInitialized = true;
            console.log('Console initialization successful');
            return true;
        } catch (error) {
            console.error('Failed to initialize console:', error);
            this.isInitialized = false;
            throw error;
        }
    }

    async findElements() {
        return new Promise((resolve, reject) => {
            const maxRetries = 10;
            const retryDelay = 100;
            let retryCount = 0;

            const findElements = () => {
                console.log('Finding console elements...');
                this.outputElement = document.getElementById('consoleOutput');
                this.inputElement = document.getElementById('consoleInput');
                this.inputLine = document.querySelector('.console-input-line');

                if (!this.outputElement || !this.inputElement || !this.inputLine) {
                    if (retryCount < maxRetries) {
                        retryCount++;
                        setTimeout(findElements, retryDelay);
                        return;
                    }
                    reject(new Error('Console elements not found'));
                    return;
                }

                this.outputElement.style.display = 'block';
                this.inputElement.style.display = 'block';
                this.inputLine.style.display = 'flex';
                resolve();
            };

            findElements();
        });
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

            if (this.outputElement) {
                this.outputElement.innerHTML = '';
            }

            if (this.inputElement) {
                this.inputElement.value = '';
                this.inputElement.disabled = true;
            }

            this.sessionId = null;
            this.isWaitingForInput = false;
            this.isSessionValid = false;
            this.pollRetryCount = 0;
            this.polling = false;
            return true;
        } catch (error) {
            console.error('Error in cleanupConsole:', error);
            return false;
        }
    }

    async executeCode(code, language) {
        console.log('executeCode called with:', { language, codeLength: code?.length });

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
            console.log('Starting new session...');

            const success = await this.startSession(code, language);
            if (!success) {
                throw new Error('Failed to start program execution');
            }

            console.log('Session started, beginning polling...');
            await this.startPolling();
            return true;
        } catch (error) {
            console.error('Error executing code:', error);
            this.appendToConsole(`Error: ${error.message}`, 'error');
            throw error;
        } finally {
            this.isBusy = false;
        }
    }

    async startSession(code, language) {
        if (!this.isInitialized) {
            throw new Error('Console not initialized');
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

            this.sessionId = data.session_id;
            this.isSessionValid = true;
            this.pollRetryCount = 0;
            return true;
        } catch (error) {
            console.error('Error in startSession:', error);
            this.appendToConsole(`Error: ${error.message}`, 'error');
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

        console.log('Starting polling for session:', this.sessionId);
        await this.poll();
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
            const response = await fetch(`/activities/get_output?session_id=${this.sessionId}`, {
                credentials: 'same-origin',
                headers: {
                    'X-CSRF-Token': this.csrfToken
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Poll response:', data);

            if (!data.success) {
                throw new Error(data.error || 'Failed to get output');
            }

            if (data.output) {
                this.appendToConsole(data.output);
            }

            if (data.session_ended) {
                console.log('Session ended');
                this.isSessionValid = false;
                this.setInputState(false);
                return;
            }

            // Reset retry count on successful poll
            this.pollRetryCount = 0;
            this.isWaitingForInput = data.waiting_for_input;
            this.setInputState(data.waiting_for_input);

            // Continue polling with immediate next request if session is valid
            if (this.isSessionValid) {
                this.pollTimer = setTimeout(() => this.poll(), 100);
            }
        } catch (error) {
            console.error('Poll error:', error);
            this.handlePollError(error);
        } finally {
            this.polling = false;
        }
    }

    handlePollError(error) {
        this.pollRetryCount++;
        console.error(`Poll error (attempt ${this.pollRetryCount}/${this.maxRetries}):`, error);

        if (this.pollRetryCount >= this.maxRetries) {
            this.isSessionValid = false;
            this.appendToConsole(`Error: Maximum polling retries reached. Please try again.`, 'error');
            if (this.pollTimer) {
                clearTimeout(this.pollTimer);
                this.pollTimer = null;
            }
            return;
        }

        const delay = this.baseDelay * Math.pow(2, this.pollRetryCount);
        console.log(`Retrying poll in ${delay}ms`);
        this.pollTimer = setTimeout(() => this.poll(), delay);
    }

    appendToConsole(text, type = 'output') {
        if (!text || !this.outputElement) {
            return;
        }

        console.log('Appending to console:', { text, type });

        const lines = text.split('\n');
        lines.forEach(line => {
            if (line.trim()) {
                const lineElement = document.createElement('div');
                lineElement.className = `console-${type}`;
                lineElement.textContent = type === 'input' ? `> ${line}` : line;
                this.outputElement.appendChild(lineElement);
            }
        });

        // Scroll to bottom
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    setupEventListeners() {
        if (!this.inputElement) {
            return;
        }

        const handleEnter = async (e) => {
            if (e.key === 'Enter' && this.isWaitingForInput && this.isSessionValid) {
                e.preventDefault();
                const inputText = this.inputElement.value.trim();
                if (inputText) {
                    this.appendToConsole(inputText, 'input');
                    await this.sendInput(inputText + '\n');
                }
            }
        };

        this.inputElement.addEventListener('keypress', handleEnter);

        const handleBlur = () => {
            if (this.isWaitingForInput && this.isSessionValid) {
                this.inputElement.focus();
            }
        };

        this.inputElement.addEventListener('blur', handleBlur);
    }

    async sendInput(input) {
        if (!this.sessionId || !this.isSessionValid) {
            console.error('Cannot send input: invalid session');
            return;
        }

        try {
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
        } catch (error) {
            console.error('Error sending input:', error);
            this.appendToConsole('Error: Failed to send input', 'error');
        }
    }
}

// Export to window
window.InteractiveConsole = InteractiveConsole;