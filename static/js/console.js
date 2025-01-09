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
            await this.findElements();
            this.setupEventListeners();
            await this.cleanupConsole();
            this.isInitialized = true;
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

            const success = await this.startSession(code, language);
            if (!success) {
                throw new Error('Failed to start program execution');
            }

            await this.startPolling();
            return true;
        } catch (error) {
            console.error('Error executing code:', error);
            throw error;
        } finally {
            this.isBusy = false;
        }
    }

    async startSession(code, language) {
        if (!this.isInitialized) {
            throw new Error('Console not initialized');
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

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
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
            return;
        }

        if (this.polling) {
            return;
        }

        this.polling = true;

        try {
            const response = await fetch(`/activities/get_output?session_id=${this.sessionId}`, {
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            if (!data.success) {
                throw new Error(data.error || 'Failed to get output');
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
        if (this.pollRetryCount >= this.maxRetries) {
            this.isSessionValid = false;
            this.appendToConsole(`Error: ${error.message}`, 'error');
            return;
        }

        const delay = this.baseDelay * Math.pow(2, this.pollRetryCount);
        this.pollTimer = setTimeout(() => this.poll(), delay);
    }

    async endSession() {
        if (!this.sessionId) {
            return;
        }

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
            console.error('Error ending session:', error);
        } finally {
            if (this.pollTimer) {
                clearTimeout(this.pollTimer);
                this.pollTimer = null;
            }
            this.sessionId = null;
            this.isSessionValid = false;
        }
    }

    setInputState(waiting) {
        if (!this.inputElement || !this.inputLine) {
            return;
        }

        this.inputLine.style.display = 'flex';
        this.inputElement.style.display = 'block';
        this.isWaitingForInput = waiting;
        this.inputElement.disabled = !waiting;

        if (waiting) {
            this.inputElement.focus();
        }
    }

    appendToConsole(text, type = 'output') {
        if (!text || !this.outputElement) {
            return;
        }

        const line = document.createElement('div');
        line.className = `console-${type}`;
        line.textContent = type === 'input' ? `> ${text}` : text;

        this.outputElement.appendChild(line);
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