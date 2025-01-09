/**
 * Interactive Console class for handling real-time program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        console.log("Initializing InteractiveConsole");
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

        this.setupEventListeners();
        this.isInitialized = true;
        console.log("InteractiveConsole initialized successfully");
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
        return this.isInitialized && this.csrfToken && !this.isBusy;
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

    async executeCode(code, language) {
        console.log("executeCode called:", { language, codeLength: code?.length });

        if (!this.isReady()) {
            console.error("Console not ready");
            throw new Error("Console not ready. Please try again.");
        }

        if (!code?.trim()) {
            console.error("Empty code submission");
            throw new Error("No code to execute");
        }

        this.isBusy = true;

        try {
            // Clean up any existing session first
            if (this.pollTimer) {
                clearTimeout(this.pollTimer);
                this.pollTimer = null;
            }

            if (this.sessionId) {
                console.log("Cleaning up existing session");
                await this.endSession();
            }

            // Start new session
            console.log("Starting new session");
            const success = await this.startSession(code, language);

            if (!success) {
                console.error("Failed to start session");
                throw new Error("Failed to start program execution");
            }

            console.log("Session started successfully, beginning output polling");
            this.startPolling();

        } catch (error) {
            console.error("Error in executeCode:", error);
            this.isBusy = false;
            throw error;
        }
    }

    startPolling() {
        console.log("Starting polling cycle");
        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
        }
        this.poll();
    }

    async startSession(code, language) {
        console.log("startSession called:", { language, codeLength: code?.length });

        try {
            console.log("Sending start_session request");
            const response = await fetch('/activities/start_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                credentials: 'same-origin',
                body: JSON.stringify({ code, language })
            });

            console.log("Received start_session response:", response.status);
            const data = await response.json();
            console.log("Response data:", data);

            if (!response.ok || !data.success) {
                console.error("Start session failed:", data.error);
                return false;
            }

            this.sessionId = data.session_id;
            this.isSessionValid = true;
            this.pollRetryCount = 0;
            console.log("Session started successfully:", this.sessionId);
            return true;

        } catch (error) {
            console.error("Error in startSession:", error);
            return false;
        }
    }

    async poll() {
        if (!this.sessionId || !this.isSessionValid) {
            console.log("Polling stopped: invalid session state");
            return;
        }

        try {
            console.log("Polling for output");
            const response = await fetch(`/activities/get_output?session_id=${this.sessionId}`, {
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error('Failed to get output');
            }

            const data = await response.json();
            console.log("Poll response:", data);

            if (data.success) {
                this.pollRetryCount = 0;

                if (data.output) {
                    console.log("Received output:", data.output);
                    this.appendToConsole(data.output);
                }

                if (data.session_ended) {
                    console.log("Session ended normally");
                    await this.endSession();
                    return;
                }

                this.setInputState(data.waiting_for_input);

                if (this.isSessionValid && this.sessionId) {
                    this.pollTimer = setTimeout(() => this.poll(), this.baseDelay);
                }
            } else {
                console.error("Poll failed:", data.error);
                this.handlePollError(data.error);
            }
        } catch (error) {
            console.error("Error in poll:", error);
            this.handlePollError(error.message);
        }
    }

    handlePollError(error) {
        this.pollRetryCount++;
        if (this.pollRetryCount >= this.maxRetries) {
            if (error?.includes('Invalid session')) {
                this.isSessionValid = false;
                this.appendToConsole(`Session ended\n`, 'system');
            } else {
                this.appendToConsole(`Error: ${error || 'Connection lost'}\n`, 'error');
            }
            this.endSession();
        } else {
            this.pollTimer = setTimeout(() => this.poll(), this.baseDelay * Math.pow(2, this.pollRetryCount));
        }
    }

    async endSession() {
        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
            this.pollTimer = null;
        }

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
                console.error("Error ending session:", error);
            }
        }

        this.sessionId = null;
        this.isSessionValid = false;
        this.setInputState(false);
        this.inputQueue = [];
        this.pollRetryCount = 0;
        this.isBusy = false;
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