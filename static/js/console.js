/**
 * Interactive Console class for handling real-time program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.outputElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');
        this.inputLine = document.querySelector('.console-input-line');

        if (!this.outputElement || !this.inputElement) {
            throw new Error('Console elements not found');
        }

        // Get CSRF token from meta tag
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        this.csrfToken = metaToken ? metaToken.content : null;

        if (!this.csrfToken) {
            throw new Error('CSRF token not found');
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
        this.isBusy = false;
        this.pollTimer = null;
        this.cleanupInProgress = false;

        // Initialize and mark as ready
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
    }

    isReady() {
        return this.isInitialized && this.csrfToken && !this.cleanupInProgress;
    }

    setInputState(waiting) {
        this.isWaitingForInput = waiting && this.isSessionValid;
        this.inputElement.disabled = !this.isWaitingForInput;

        if (this.inputLine) {
            this.inputLine.classList.toggle('console-waiting', this.isWaitingForInput);
            if (this.isWaitingForInput) {
                this.inputElement.focus();
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

    async executeCode(code, language) {
        if (!this.isReady()) {
            throw new Error("Console not ready. Please wait a moment.");
        }

        if (!code?.trim()) {
            throw new Error("No code to execute");
        }

        if (this.isBusy) {
            throw new Error("Already executing code. Please wait.");
        }

        this.isBusy = true;

        try {
            // Clear console first
            this.outputElement.innerHTML = '';
            this.appendToConsole("Initializing...\n", 'system');

            // Clean up existing session
            await this.endSession();

            // Start new session
            this.appendToConsole("Compiling and running code...\n", 'system');
            const success = await this.startSession(code, language);

            if (!success) {
                throw new Error("Failed to start program execution");
            }

            // Begin output polling
            this.startPolling();
            return true;

        } catch (error) {
            console.error("Error in executeCode:", error);
            this.appendToConsole(`Error: ${error.message}\n`, 'error');
            throw error;
        }
    }

    async startSession(code, language) {
        if (!code || !language) return false;

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
                throw new Error("Failed to start session");
            }

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || "Failed to start session");
            }

            this.sessionId = data.session_id;
            this.isSessionValid = true;
            this.pollRetryCount = 0;
            return true;

        } catch (error) {
            console.error("Error in startSession:", error);
            return false;
        }
    }

    startPolling() {
        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
        }
        this.pollTimer = setTimeout(() => this.poll(), 100); // Small initial delay
    }

    async poll() {
        if (!this.sessionId || !this.isSessionValid) {
            return;
        }

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
                    this.pollTimer = setTimeout(() => this.poll(), this.baseDelay);
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
            this.isSessionValid = false;
            this.endSession();
        } else {
            this.pollTimer = setTimeout(() => this.poll(), 
                this.baseDelay * Math.pow(2, this.pollRetryCount));
        }
    }

    async endSession() {
        this.cleanupInProgress = true;

        try {
            if (this.pollTimer) {
                clearTimeout(this.pollTimer);
                this.pollTimer = null;
            }

            if (this.sessionId) {
                try {
                    await fetch('/activities/end_session', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRF-Token': this.csrfToken
                        },
                        credentials: 'same-origin',
                        body: JSON.stringify({ session_id: this.sessionId })
                    });
                } catch (error) {
                    console.error("Error ending session:", error);
                }
            }
        } finally {
            this.sessionId = null;
            this.isSessionValid = false;
            this.setInputState(false);
            this.inputQueue = [];
            this.pollRetryCount = 0;
            this.isBusy = false;
            this.cleanupInProgress = false;
        }
    }

    async sendInput(input) {
        if (!this.sessionId || !this.isSessionValid) return;

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
            if (!data.success) {
                throw new Error(data.error || 'Failed to send input');
            }
        } catch (error) {
            console.error("Error sending input:", error);
            this.handlePollError(error.message);
        }
    }
}

// Export for use in other files
window.InteractiveConsole = InteractiveConsole;