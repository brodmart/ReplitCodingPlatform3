/**
 * Interactive Console class for handling real-time program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.outputElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');
        this.inputLine = document.querySelector('.console-input-line');

        if (!this.outputElement || !this.inputElement) {
            console.error('Console elements not found');
            return;
        }

        this.sessionId = null;
        this.isWaitingForInput = false;
        this.lang = options.lang || 'en';
        this.inputQueue = [];
        this.pollRetryCount = 0;
        this.maxRetries = 3;
        this.baseDelay = 100;
        this.isSessionValid = true;
        this.isInitialized = false;
        this.isClearing = false;

        // Get CSRF token from meta tag
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        this.csrfToken = metaToken ? metaToken.content : null;

        if (!this.csrfToken) {
            console.error('CSRF token not found');
            this.appendToConsole("Error: Security token missing. Please refresh the page.", 'error');
            return;
        }

        this.setupEventListeners();
        this.isInitialized = true;
    }

    setupEventListeners() {
        this.inputElement.addEventListener('keypress', async (e) => {
            if (e.key === 'Enter' && this.isWaitingForInput && this.isSessionValid) {
                e.preventDefault();
                const inputText = this.inputElement.value;
                this.inputElement.value = '';
                this.setInputState(false);
                this.appendToConsole(`${inputText}\n`, 'input');

                if (this.sessionId) {
                    await this.sendInput(inputText);
                }
            }
        });

        this.inputElement.addEventListener('paste', (e) => {
            if (this.isWaitingForInput && this.isSessionValid) {
                e.preventDefault();
                const pastedText = e.clipboardData.getData('text');
                const lines = pastedText.split('\n');

                if (lines.length > 1) {
                    this.inputQueue.push(...lines.filter(line => line.trim()));
                    this.processInputQueue();
                } else {
                    this.inputElement.value = pastedText;
                }
            }
        });
    }

    isReady() {
        return this.isInitialized && this.csrfToken && !this.isClearing;
    }

    setInputState(waiting) {
        this.isWaitingForInput = waiting && this.isSessionValid;
        this.inputElement.disabled = !this.isWaitingForInput;

        if (this.inputLine) {
            if (this.isWaitingForInput) {
                this.inputLine.classList.add('console-waiting');
                this.inputElement.focus();
            } else {
                this.inputLine.classList.remove('console-waiting');
            }
        }
    }

    appendToConsole(text, type = 'output') {
        if (!text) return;

        const line = document.createElement('div');
        line.className = `console-${type}`;
        line.textContent = type === 'input' ? `> ${text}` : text;
        this.outputElement.appendChild(line);
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    async clear() {
        if (this.isClearing) {
            return false;
        }

        this.isClearing = true;
        try {
            if (this.sessionId) {
                await this.endSession();
            }

            if (this.outputElement) {
                this.outputElement.innerHTML = '';
            }

            this.setInputState(false);
            this.inputQueue = [];
            this.pollRetryCount = 0;
            this.sessionId = null;
            this.isSessionValid = true;

            return true;
        } finally {
            this.isClearing = false;
        }
    }

    async executeCode(code, language) {
        if (!this.isReady()) {
            this.appendToConsole("Error: Console not ready. Please refresh the page.", 'error');
            return false;
        }

        if (!code?.trim()) {
            this.appendToConsole("Error: No code to execute\n", 'error');
            return false;
        }

        await this.clear();
        return await this.startSession(code, language);
    }

    async startSession(code, language) {
        if (!this.isReady()) {
            this.appendToConsole("Error: Console not ready. Please refresh the page.", 'error');
            return false;
        }

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

            const data = await response.json();
            if (!response.ok) {
                this.appendToConsole(`Error: ${data.error || 'Failed to start session'}\n`, 'error');
                return false;
            }

            if (data.success) {
                this.sessionId = data.session_id;
                this.isSessionValid = true;
                this.pollRetryCount = 0;
                this.poll();
                return true;
            } else {
                this.appendToConsole(`Error: ${data.error || 'Failed to start session'}\n`, 'error');
                return false;
            }
        } catch (error) {
            this.appendToConsole(`Error: ${error.message}\n`, 'error');
            return false;
        }
    }

    async poll() {
        if (!this.sessionId || !this.isSessionValid) return;

        try {
            const response = await fetch(`/activities/get_output?session_id=${this.sessionId}`, {
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error('Failed to get output');
            }

            const data = await response.json();
            if (data.success) {
                this.pollRetryCount = 0;

                if (data.output) {
                    this.appendToConsole(data.output);
                }

                if (data.session_ended) {
                    await this.endSession();
                    return;
                }

                this.setInputState(data.waiting_for_input);

                if (this.isSessionValid && this.sessionId) {
                    setTimeout(() => this.poll(), this.baseDelay);
                }
            } else {
                this.handlePollError(data.error);
            }
        } catch (error) {
            this.handlePollError(error.message);
        }
    }

    handlePollError(error) {
        this.pollRetryCount++;
        if (this.pollRetryCount >= this.maxRetries) {
            if (error?.includes('Invalid session')) {
                this.isSessionValid = false;
                this.appendToConsole(`Session ended\n`, 'error');
            } else {
                this.appendToConsole(`Error: ${error || 'Connection lost'}\n`, 'error');
            }
            this.endSession();
        } else {
            setTimeout(() => this.poll(), this.baseDelay * Math.pow(2, this.pollRetryCount));
        }
    }

    async sendInput(input) {
        if (!this.sessionId || !this.csrfToken || !this.isSessionValid) return;

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
                    input: input
                })
            });

            const data = await response.json();
            if (!response.ok || !data.success) {
                if (data.error?.includes('Invalid session')) {
                    this.isSessionValid = false;
                    this.appendToConsole(`Session ended\n`, 'error');
                    await this.endSession();
                    return;
                }
                this.appendToConsole(`Error: ${data.error || 'Failed to send input'}\n`, 'error');
            }

            this.processInputQueue();
        } catch (error) {
            this.appendToConsole(`Error: ${error.message}\n`, 'error');
            await this.endSession();
        }
    }

    async endSession() {
        if (this.sessionId && this.csrfToken) {
            try {
                await fetch('/activities/end_session', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': this.csrfToken
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        session_id: this.sessionId
                    })
                });
            } catch (error) {
                console.error('Error ending session:', error);
            }
        }

        this.sessionId = null;
        this.isSessionValid = false;
        this.setInputState(false);
        this.inputQueue = [];
        this.pollRetryCount = 0;
    }

    async processInputQueue() {
        if (this.inputQueue.length > 0 && this.isWaitingForInput && this.isSessionValid) {
            const input = this.inputQueue.shift();
            this.inputElement.value = input;
            const event = new KeyboardEvent('keypress', { key: 'Enter' });
            this.inputElement.dispatchEvent(event);
        }
    }
}

// Export for use in other files
window.InteractiveConsole = InteractiveConsole;