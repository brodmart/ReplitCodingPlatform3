/**
 * Interactive Console class for handling real-time program I/O
 */
class InteractiveConsole {
    constructor() {
        console.log('Initializing InteractiveConsole');
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
        this.maxRetries = 5;
        this.currentPollInterval = 100;
        this.baseDelay = 100;
        this.maxPollInterval = 2000;
        this.backoffFactor = 1.5;

        // Get CSRF token
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        this.csrfToken = metaToken ? metaToken.content : null;

        if (!this.csrfToken) {
            console.error('CSRF token not found');
            throw new Error('CSRF token not found');
        }

        // Add debounce timer
        this.stateUpdateTimer = null;
        this.stateUpdateDelay = 100;

        // Track consecutive empty polls
        this.emptyPollCount = 0;
        this.maxEmptyPolls = 3;
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
            this.emptyPollCount = 0; // Reset empty poll count
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

        // Show compilation progress
        this.appendToConsole('Starting compilation...', 'info');
        if (code.length > 50000) {
            this.appendToConsole('Large code submission detected, this may take longer...', 'info');
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

            this.appendToConsole('Compilation successful', 'info');
            if (data.compilation_time) {
                this.appendToConsole(`Compiled in ${data.compilation_time.toFixed(2)}s`, 'info');
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

        // Reset polling parameters
        this.currentPollInterval = this.baseDelay;
        this.pollRetryCount = 0;
        this.emptyPollCount = 0; // Reset empty poll counter

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

            // Reset input field but keep session valid
            this.inputElement.value = '';
            this.inputElement.focus();

            // Don't disable input immediately, wait for next poll
            // This ensures we catch any immediate program output
            this.currentPollInterval = this.baseDelay;
            await this.poll(); // Immediate poll to catch the response
        } catch (error) {
            console.error('Error sending input:', error);
            this.appendToConsole('Error: Failed to send input', 'error');
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

            // Handle output if present
            if (data.output) {
                console.log('Received output:', data.output);
                this.appendToConsole(data.output);
                this.emptyPollCount = 0;

                // Reset poll interval when we get output
                this.currentPollInterval = this.baseDelay;

                // If output contains input prompt, force input state
                if (data.output.includes('Enter') || data.output.includes('Input')) {
                    data.waiting_for_input = true;
                }
            } else {
                this.emptyPollCount++;
            }

            if (data.session_ended) {
                console.log('Session ended');
                this.isSessionValid = false;
                this.setInputState(false);
                return;
            }

            // Prevent rapid state changes
            if (data.waiting_for_input !== this.isWaitingForInput) {
                console.log('Input state change requested:', data.waiting_for_input);

                // Clear any pending state updates
                if (this.stateUpdateTimer) {
                    clearTimeout(this.stateUpdateTimer);
                }

                // If enabling input, do it immediately
                if (data.waiting_for_input) {
                    this.setInputState(true);
                    this.inputElement.style.display = 'block';
                    this.inputLine.style.display = 'flex';
                    this.inputElement.focus();
                } else {
                    // Only disable input if we've received all output
                    this.stateUpdateTimer = setTimeout(() => {
                        // Double check we're not waiting for more output
                        if (!this.isWaitingForInput && this.emptyPollCount > 1) {
                            this.setInputState(false);
                        }
                    }, 2000); // Longer wait to ensure we catch all output
                }
            }

            // Adjust polling interval based on state and output
            const nextPollDelay = this.isWaitingForInput ? 2000 : // Longer delay when waiting for input
                this.emptyPollCount > this.maxEmptyPolls ? 1000 : // Medium delay when no output
                    this.currentPollInterval; // Base delay when actively receiving output

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

        // Implement exponential backoff
        this.currentPollInterval = Math.min(
            this.currentPollInterval * this.backoffFactor,
            this.maxPollInterval
        );

        console.log(`Retrying poll in ${this.currentPollInterval}ms`);
        this.pollTimer = setTimeout(() => this.poll(), this.currentPollInterval);
    }

    appendToConsole(text, type = 'output') {
        if (!text || !this.outputElement) {
            console.log('Cannot append to console - missing text or element:', {
                hasText: !!text,
                hasElement: !!this.outputElement
            });
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
                console.log('Added line to console:', line);
            }
        });

        // Scroll to bottom
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
        console.log('Console scrolled to bottom');
    }

    setupEventListeners() {
        if (!this.inputElement) {
            return;
        }
        
        // Ensure console respects parent container width
        const consoleContainer = document.querySelector('.console-container');
        if (consoleContainer) {
            consoleContainer.style.width = '100%';
            consoleContainer.style.maxWidth = 'none';
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


    setInputState(enabled) {
        if (!this.inputElement) {
            console.error('Input element not found');
            return;
        }

        console.log('Setting input state:', enabled);

        // Always update the visual state when enabled
        if (enabled) {
            this.isWaitingForInput = true;
            this.inputElement.disabled = false;
            this.inputElement.value = '';
            this.inputElement.style.display = 'block';
            this.inputLine.style.display = 'flex';
            this.inputElement.focus();
            this.inputLine.classList.add('active');

            // Update console container state
            const consoleContainer = document.querySelector('.console-container');
            if (consoleContainer) {
                consoleContainer.classList.add('console-waiting');
            }

            // Force persist input state
            sessionStorage.setItem('console_input_state', JSON.stringify({
                isWaiting: true,
                timestamp: Date.now()
            }));

            // Set a minimum duration for input state
            if (this.inputStateTimer) {
                clearTimeout(this.inputStateTimer);
            }
            this.inputStateTimer = setTimeout(() => {
                this.inputStateTimer = null;
            }, 5000); // Keep input active for at least 5 seconds
        } else {
            // Only disable if there's no pending input timer
            if (!this.inputStateTimer && this.isWaitingForInput) {
                this.isWaitingForInput = false;
                this.inputElement.disabled = true;
                this.inputLine.classList.remove('active');

                const consoleContainer = document.querySelector('.console-container');
                if (consoleContainer) {
                    consoleContainer.classList.remove('console-waiting');
                }

                sessionStorage.removeItem('console_input_state');
            }
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