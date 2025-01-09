/**
 * Interactive Console class for handling real-time program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        // DOM elements
        this.outputElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');
        this.inputLine = document.querySelector('.console-input-line');

        if (!this.outputElement || !this.inputElement || !this.inputLine) {
            throw new Error('Console elements not found');
        }

        // Get CSRF token
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        this.csrfToken = metaToken ? metaToken.content : null;

        if (!this.csrfToken) {
            throw new Error('CSRF token not found');
        }

        // Initialize state
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

        // Initialize immediately
        this.init();
    }

    init() {
        return new Promise((resolve, reject) => {
            try {
                // Wait for DOM
                if (!this.outputElement || !this.inputLine || !this.inputElement) {
                    reject(new Error('Required elements not found'));
                    return;
                }

                // Reset and force visibility immediately
                this.cleanupConsole();
                this.outputElement.style.display = 'block';
                this.inputLine.style.display = 'flex';
                this.inputElement.style.display = 'block';
                this.inputElement.style.visibility = 'visible';
                
                // Setup event listeners
                this.setupEventListeners();
                this.setInputState(false);

                // Ensure visibility persists
                requestAnimationFrame(() => {
                    this.outputElement.style.display = 'block';
                    this.inputLine.style.display = 'flex';
                    this.inputElement.style.display = 'block';
                    this.inputElement.style.visibility = 'visible';
                    
                    // Mark as initialized and resolve
                    this.isInitialized = true;
                    resolve();
                });

            console.log('Console initialized successfully');
        } catch (error) {
            console.error('Failed to initialize console:', error);
            throw error;
        }
    }

    cleanupConsole() {
        this.outputElement.innerHTML = '';
        this.inputElement.value = '';
        
        // Force visibility state
        this.inputLine.style.display = 'flex';
        this.inputElement.style.display = 'block';
        this.inputElement.style.visibility = 'visible';
        this.inputElement.disabled = true;
        
        // Reset state
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.isSessionValid = false;
        this.pollRetryCount = 0;
        
        // Clear any pending polls
        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
            this.pollTimer = null;
        }
    }

    setupEventListeners() {
        if (!this.inputElement) return;

        // Handle Enter key press
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

        this.inputElement.removeEventListener('keypress', handleEnter);
        this.inputElement.addEventListener('keypress', handleEnter);

        // Keep focus on input when needed
        const handleBlur = () => {
            if (this.isWaitingForInput && this.isSessionValid) {
                this.inputElement.focus();
            }
        };

        this.inputElement.removeEventListener('blur', handleBlur);
        this.inputElement.addEventListener('blur', handleBlur);
    }

    setInputState(waiting) {
        if (!this.inputElement || !this.inputLine) {
            console.error('Input elements not available');
            return;
        }

        console.log('Setting input state to waiting:', waiting);

        // Force elements to always be visible
        this.inputLine.style.display = 'flex';
        this.inputElement.style.display = 'block';

        // Update state and enable/disable
        this.isWaitingForInput = waiting;
        this.inputElement.disabled = !waiting;
        this.isSessionValid = waiting;

        if (this.isWaitingForInput) {
            this.inputElement.focus();
            this.outputElement.scrollTop = this.outputElement.scrollHeight;
        }

        console.log('Input state updated:', {
            waiting: this.isWaitingForInput,
            sessionValid: this.isSessionValid,
            inputEnabled: !this.inputElement.disabled
        });
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
        if (!this.isInitialized) {
            throw new Error("Console not initialized");
        }

        if (!code?.trim()) {
            throw new Error("No code to execute");
        }

        this.isBusy = true;

        try {
            // Only end previous session if one exists
            if (this.sessionId) {
                await this.endSession();
            }

            // Keep input elements visible but disabled during transition
            this.inputLine.style.display = 'flex';
            this.inputElement.style.display = 'block';
            this.inputElement.disabled = true;

            // Clean output
            this.outputElement.innerHTML = '';

            const success = await this.startSession(code, language);
            if (!success) {
                throw new Error("Failed to start program execution");
            }

            this.startPolling();
            return true;

        } catch (error) {
            console.error("Error executing code:", error);
            throw error;
        } finally {
            this.isBusy = false;
        }
    }

    async startSession(code, language) {
        try {
            console.log('Starting new session:', { language, codeLength: code.length });

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
        this.poll();
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
            console.log("Poll response:", data);

            if (data.success) {
                this.pollRetryCount = 0;

                // Show output if present
                if (data.output) {
                    this.appendToConsole(data.output);
                }

                // Handle session state
                if (data.session_ended) {
                    this.isSessionValid = false;
                    this.isWaitingForInput = false;
                    this.inputElement.disabled = true;
                    this.inputElement.value = '';
                    return;
                }

                // Update input state
                this.isSessionValid = true;
                if (data.waiting_for_input) {
                    this.isWaitingForInput = true;
                    this.inputElement.disabled = false;
                    this.inputElement.focus();
                    this.outputElement.scrollTop = this.outputElement.scrollHeight;
                }

                // Continue polling if session is active
                if (this.isSessionValid && this.sessionId) {
                    this.pollTimer = setTimeout(() => this.poll(), this.baseDelay);
                }
            } else {
                this.handlePollError(data.error || 'Unknown error');
            }
        } catch (error) {
            this.handlePollError(error.message);
        }
    }

    handlePollError(error) {
        console.error("Poll error:", error);
        this.pollRetryCount++;

        if (this.pollRetryCount >= this.maxRetries) {
            console.log('Max retries reached, ending session');
            this.isSessionValid = false;
            this.endSession();
        } else {
            const delay = this.baseDelay * Math.pow(2, this.pollRetryCount);
            console.log(`Retrying poll in ${delay}ms`);
            this.pollTimer = setTimeout(() => this.poll(), delay);
        }
    }

    async endSession() {
        if (!this.sessionId && !this.pollTimer) {
            return;
        }

        console.log('Ending session:', this.sessionId);

        try {
            if (this.pollTimer) {
                clearTimeout(this.pollTimer);
                this.pollTimer = null;
            }

            if (this.sessionId) {
                await fetch('/activities/end_session', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': this.csrfToken
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({ session_id: this.sessionId })
                });
            }
        } catch (error) {
            console.error("Error ending session:", error);
        } finally {
            this.cleanupConsole();
            this.isBusy = false;
        }
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
                    input: input + '\n'
                })
            });

            const data = await response.json();
            if (!data.success) {
                throw new Error(data.error || 'Failed to send input');
            }

            // Clear input field but don't change state
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