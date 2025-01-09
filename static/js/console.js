/**
 * Interactive Console class for handling real-time program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.outputElement = null;
        this.inputElement = null;
        this.inputLine = null;
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.lang = options.lang || 'en';
        this.pollRetryCount = 0;
        this.maxRetries = 3;
        this.baseDelay = 100;
        this.isSessionValid = false;
        this.isInitialized = false;
        this.isBusy = false;
        this.pollTimer = null;
        this.polling = false;

        // Get CSRF token
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        this.csrfToken = metaToken ? metaToken.content : null;

        if (!this.csrfToken) {
            throw new Error('CSRF token not found');
        }
    }

    async init() {
        try {
            await this.findElements();
            this.setupEventListeners();
            this.cleanupConsole();
            this.isInitialized = true;
            console.log('Console initialized successfully');
            window.dispatchEvent(new Event('consoleReady'));
        } catch (error) {
            console.error('Failed to initialize console:', error);
            throw error;
        }
    }

    async findElements() {
        return new Promise((resolve, reject) => {
            const maxRetries = 10;
            const retryDelay = 100;
            let retryCount = 0;

            const findElements = () => {
                this.outputElement = document.getElementById('consoleOutput');
                this.inputElement = document.getElementById('consoleInput');
                this.inputLine = document.querySelector('.console-input-line');

                if (!this.outputElement || !this.inputElement || !this.inputLine) {
                    if (retryCount < maxRetries) {
                        retryCount++;
                        setTimeout(findElements, retryDelay);
                        return;
                    }
                    reject(new Error('Console elements not found after maximum retries'));
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

    cleanupConsole() {
        if (this.outputElement) {
            this.outputElement.innerHTML = '';
        }
        if (this.inputElement) {
            this.inputElement.value = '';
        }
        if (this.inputLine) {
            this.inputLine.style.display = 'flex';
            this.inputElement.style.display = 'block';
            this.inputElement.disabled = true;
        }

        this.sessionId = null;
        this.isWaitingForInput = false;
        this.isSessionValid = false;
        this.pollRetryCount = 0;
        this.polling = false;

        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
            this.pollTimer = null;
        }
    }

    async executeCode(code, language) {
        if (!this.isInitialized) {
            throw new Error("Console not initialized");
        }

        if (!code?.trim()) {
            throw new Error("No code to execute");
        }

        if (this.isBusy) {
            throw new Error("Console is busy");
        }

        try {
            this.isBusy = true;

            // Clean up any existing session
            await this.endSession();

            // Start new session
            const success = await this.startSession(code, language);
            if (!success) {
                throw new Error("Failed to start program execution");
            }

            // Begin polling for output
            await this.startPolling();
            return true;
        } catch (error) {
            console.error("Error executing code:", error);
            throw error;
        } finally {
            this.isBusy = false;
        }
    }

    async startSession(code, language) {
        console.log('Starting new session:', { language, codeLength: code.length });

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
                throw new Error(`Failed to start session: ${response.status}`);
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

    async startPolling() {
        if (!this.sessionId || !this.isSessionValid) {
            console.log('Session not valid for polling');
            return;
        }

        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
            this.pollTimer = null;
        }

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

        try {
            const response = await fetch(`/activities/get_output?session_id=${this.sessionId}`, {
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`Failed to get output: ${response.status}`);
            }

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || "Failed to get output");
            }

            if (data.output) {
                this.appendToConsole(data.output);
            }

            if (data.session_ended) {
                this.isSessionValid = false;
                this.setInputState(false);
                return;
            }

            this.pollRetryCount = 0;
            this.isWaitingForInput = data.waiting_for_input;
            this.setInputState(data.waiting_for_input);

            // Schedule next poll
            if (this.isSessionValid) {
                this.pollTimer = setTimeout(() => this.poll(), this.baseDelay);
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
            console.log('Max retries reached, ending session');
            this.isSessionValid = false;
            this.endSession();
            return;
        }

        const delay = this.baseDelay * Math.pow(2, this.pollRetryCount);
        console.log(`Retrying poll in ${delay}ms`);
        this.pollTimer = setTimeout(() => this.poll(), delay);
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
                    console.error('Failed to end session:', response.status);
                }
            }
        } catch (error) {
            console.error("Error ending session:", error);
        } finally {
            this.cleanupConsole();
        }
    }

    setInputState(waiting) {
        if (!this.inputElement || !this.inputLine) return;

        this.inputLine.style.display = 'flex';
        this.inputElement.style.display = 'block';
        this.isWaitingForInput = waiting;
        this.inputElement.disabled = !waiting;

        if (waiting) {
            this.inputElement.focus();
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

    setupEventListeners() {
        if (!this.inputElement) return;

        const handleEnter = async (e) => {
            if (e.key === 'Enter' && this.isWaitingForInput && this.isSessionValid) {
                e.preventDefault();
                const inputText = this.inputElement.value.trim();
                if (inputText) {
                    this.appendToConsole(`${inputText}\n`, 'input');
                    this.inputElement.value = '';
                    await this.sendInput(inputText);
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
                    input: input + '\n'
                })
            });

            const data = await response.json();
            if (!data.success) {
                throw new Error(data.error || 'Failed to send input');
            }

            this.inputElement.value = '';
            this.inputElement.focus();
        } catch (error) {
            console.error("Error sending input:", error);
            this.appendToConsole("Error: Failed to send input\n", 'error');
        }
    }
}

// Export to window
window.InteractiveConsole = InteractiveConsole;