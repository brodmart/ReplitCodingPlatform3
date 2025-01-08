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
        this.outputPoller = null;
        this.isWaitingForInput = false;
        this.lang = options.lang || 'en';
        this.inputQueue = [];
        this.pollRetryCount = 0;
        this.maxRetries = 3;
        this.baseDelay = 100;
        this.setupEventListeners();
        this.csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

        if (!this.csrfToken) {
            console.error('CSRF token not found');
        }
    }

    setupEventListeners() {
        this.inputElement.addEventListener('keypress', async (e) => {
            if (e.key === 'Enter' && this.isWaitingForInput) {
                e.preventDefault();
                const inputText = this.inputElement.value;
                this.inputElement.value = '';
                this.setInputState(false);
                this.appendToConsole(`${inputText}\n`, 'input');

                if (this.sessionId) {
                    await this.sendInput(inputText + '\n');
                }
            }
        });

        this.inputElement.addEventListener('focus', () => {
            if (!this.isWaitingForInput) {
                this.inputElement.blur();
            }
        });

        this.inputElement.addEventListener('paste', (e) => {
            if (this.isWaitingForInput) {
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

    setInputState(waiting) {
        this.isWaitingForInput = waiting;
        this.inputElement.disabled = !waiting;

        if (this.inputLine) {
            if (waiting) {
                this.inputLine.classList.add('console-waiting');
                this.inputElement.focus();
            } else {
                this.inputLine.classList.remove('console-waiting');
                this.inputElement.blur();
            }
        }
    }

    async processInputQueue() {
        if (this.inputQueue.length > 0 && this.isWaitingForInput) {
            const input = this.inputQueue.shift();
            this.inputElement.value = input;
            const event = new KeyboardEvent('keypress', { key: 'Enter' });
            this.inputElement.dispatchEvent(event);
        }
    }

    appendToConsole(text, type = 'output') {
        const line = document.createElement('div');
        line.className = `console-${type}`;
        line.textContent = type === 'input' ? `> ${text}` : text;
        this.outputElement.appendChild(line);
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    clear() {
        if (this.outputElement) {
            this.outputElement.innerHTML = '';
        }
        this.setInputState(false);
        this.endSession();
        this.pollRetryCount = 0;
    }

    async startSession(code, language) {
        this.clear();
        if (!code?.trim()) {
            this.appendToConsole(this.lang === 'fr' ?
                "Erreur: Aucun code à exécuter\n" :
                "Error: No code to execute\n", 'error');
            return false;
        }

        try {
            const response = await fetch('/activities/start_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                body: JSON.stringify({ code, language })
            });

            const data = await response.json();
            if (response.ok && data.success) {
                this.sessionId = data.session_id;
                this.startOutputPolling();
                return true;
            } else {
                this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${data.error || 'Failed to start session'}\n`, 'error');
                return false;
            }
        } catch (error) {
            this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${error.message}\n`, 'error');
            return false;
        }
    }

    calculateBackoffDelay() {
        return Math.min(this.baseDelay * Math.pow(2, this.pollRetryCount), 2000);
    }

    startOutputPolling() {
        if (this.outputPoller) {
            clearInterval(this.outputPoller);
        }

        const poll = async () => {
            if (!this.sessionId) {
                clearInterval(this.outputPoller);
                this.outputPoller = null;
                return;
            }

            try {
                const response = await fetch(`/activities/get_output?session_id=${this.sessionId}`);
                const data = await response.json();

                if (response.ok && data.success) {
                    this.pollRetryCount = 0;  // Reset retry count on success

                    if (data.output) {
                        this.appendToConsole(data.output);
                    }

                    if (data.session_ended) {
                        this.endSession();
                        return;
                    }

                    this.setInputState(data.waiting_for_input);
                    if (data.waiting_for_input) {
                        this.processInputQueue();
                    }
                } else {
                    this.pollRetryCount++;
                    if (this.pollRetryCount >= this.maxRetries) {
                        this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${data.error || 'Session ended unexpectedly'}\n`, 'error');
                        this.endSession();
                        return;
                    }
                }
            } catch (error) {
                this.pollRetryCount++;
                if (this.pollRetryCount >= this.maxRetries) {
                    this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}Connection lost\n`, 'error');
                    this.endSession();
                    return;
                }
            }
        };

        // Initial poll
        poll();

        // Start polling with dynamic interval
        this.outputPoller = setInterval(async () => {
            const delay = this.calculateBackoffDelay();
            await new Promise(resolve => setTimeout(resolve, delay));
            await poll();
        }, this.baseDelay);
    }

    async sendInput(input) {
        if (!this.sessionId || !this.csrfToken) return;

        try {
            const response = await fetch('/activities/send_input', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    input: input
                })
            });

            const data = await response.json();
            if (!response.ok || !data.success) {
                this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${data.error || 'Failed to send input'}\n`, 'error');
                if (response.status === 400) {
                    this.endSession();
                }
            }

            setTimeout(() => this.processInputQueue(), 100);
        } catch (error) {
            this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${error.message}\n`, 'error');
            this.endSession();
        }
    }

    endSession() {
        if (this.sessionId) {
            fetch('/activities/end_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            }).catch(console.error);

            if (this.outputPoller) {
                clearInterval(this.outputPoller);
                this.outputPoller = null;
            }

            this.sessionId = null;
            this.setInputState(false);
            this.inputQueue = [];
            this.pollRetryCount = 0;
        }
    }

    async executeCode(code, language) {
        this.clear();
        if (!code?.trim()) {
            this.appendToConsole(this.lang === 'fr' ?
                "Erreur: Aucun code à exécuter\n" :
                "Error: No code to execute\n", 'error');
            return;
        }

        this.appendToConsole(this.lang === 'fr' ?
            "Démarrage du programme...\n" :
            "Starting program...\n", 'success');

        const success = await this.startSession(code, language);
        if (!success) {
            this.appendToConsole(this.lang === 'fr' ?
                "Échec du démarrage de la session\n" :
                "Failed to start session\n", 'error');
        }
    }
}

// Export for use in other files
window.InteractiveConsole = InteractiveConsole;