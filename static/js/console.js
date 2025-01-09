/**
 * Interactive Console class for handling real-time program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.outputElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');
        this.inputLine = document.querySelector('.console-input-line');

        if (!this.outputElement || !this.inputElement || !this.inputLine) {
            throw new Error('Console elements not found');
        }

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
        this.executionPromise = null;

        // Setup event listeners immediately
        this.setupEventListeners();

        // Mark as initialized only after verifying all components
        if (this.verifyComponents()) {
            this.isInitialized = true;
        }
    }

    verifyComponents() {
        return (
            this.outputElement instanceof HTMLElement &&
            this.inputElement instanceof HTMLElement &&
            this.inputLine instanceof HTMLElement &&
            this.csrfToken &&
            typeof this.csrfToken === 'string'
        );
    }

    setupEventListeners() {
        if (!this.inputElement) return;

        // Remove any existing listeners first
        const newInput = this.inputElement.cloneNode(true);
        this.inputElement.parentNode.replaceChild(newInput, this.inputElement);
        this.inputElement = newInput;

        this.inputElement.addEventListener('keypress', async (e) => {
            if (e.key === 'Enter' && this.isWaitingForInput && this.isSessionValid) {
                e.preventDefault();
                const inputText = this.inputElement.value.trim();
                this.inputElement.value = '';

                if (inputText) {
                    this.appendToConsole(`${inputText}\n`, 'input');
                    await this.sendInput(inputText);
                }
            }
        });

        this.inputElement.addEventListener('blur', () => {
            if (this.isWaitingForInput && this.isSessionValid) {
                setTimeout(() => this.inputElement.focus(), 10);
            }
        });
    }

    isReady() {
        return (
            this.isInitialized &&
            this.verifyComponents() &&
            !this.cleanupInProgress &&
            !this.isBusy
        );
    }

    setInputState(waiting) {
        this.isWaitingForInput = waiting && this.isSessionValid;

        if (!this.inputElement || !this.inputLine) {
            console.error('Input elements not available');
            return;
        }

        this.inputElement.disabled = !this.isWaitingForInput;
        this.inputLine.style.display = this.isWaitingForInput ? 'flex' : 'none';
        this.inputElement.style.display = this.isWaitingForInput ? 'block' : 'none';

        if (this.isWaitingForInput) {
            this.inputElement.value = '';
            this.inputElement.focus();
            this.inputLine.classList.add('console-waiting');
        } else {
            this.inputLine.classList.remove('console-waiting');
        }
    }

    appendToConsole(text, type = 'output') {
        if (!text || !this.outputElement) return;

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

        this.isBusy = true;
        this.cleanupInProgress = true;

        try {
            await this.endSession();
            if (this.outputElement) {
                this.outputElement.innerHTML = '';
            }

            const success = await this.startSession(code, language);
            if (!success) {
                throw new Error("Failed to start program execution");
            }

            await new Promise(resolve => setTimeout(resolve, 300));
            this.startPolling();
            return true;

        } catch (error) {
            console.error("Error in executeCode:", error);
            throw error;
        } finally {
            this.cleanupInProgress = false;
            this.isBusy = false;
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
            console.log("Session start response:", data);

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
        this.pollTimer = setTimeout(() => this.poll(), 100);
    }

    async poll() {
        if (!this.sessionId || !this.isSessionValid || this.cleanupInProgress) {
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
            console.log("Poll response:", data);

            if (data.success) {
                this.pollRetryCount = 0;

                if (data.output) {
                    this.appendToConsole(data.output);
                }

                if (data.session_ended) {
                    await this.endSession();
                    return;
                }

                if (data.waiting_for_input && !this.isWaitingForInput) {
                    this.setInputState(true);
                }

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
        console.error("Poll error:", error);
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
        if (!this.sessionId && !this.pollTimer) {
            return;
        }

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
                    input: input + '\n'
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

window.InteractiveConsole = InteractiveConsole;