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
        this.setupEventListeners();
        this.csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

        if (!this.csrfToken) {
            console.error('CSRF token not found');
        }
    }

    setupEventListeners() {
        // Handle input submission with improved focus management
        this.inputElement.addEventListener('keypress', async (e) => {
            if (e.key === 'Enter' && this.isWaitingForInput) {
                e.preventDefault();
                const inputText = this.inputElement.value;
                this.inputElement.value = '';

                // Update UI to show input is being processed
                this.setInputState(false);
                this.appendToConsole(`${inputText}\n`, 'input');

                if (this.sessionId) {
                    await this.sendInput(inputText + '\n');  // Ensure newline is included
                }
            }
        });

        // Improved focus management
        this.inputElement.addEventListener('focus', () => {
            if (!this.isWaitingForInput) {
                this.inputElement.blur();
            }
        });

        this.inputElement.addEventListener('click', () => {
            if (this.isWaitingForInput) {
                this.inputElement.focus();
            }
        });

        // Handle paste events with queue processing
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

        if (type === 'input') {
            line.textContent = `> ${text}`;
        } else {
            line.textContent = text;
        }

        this.outputElement.appendChild(line);
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    clear() {
        if (this.outputElement) {
            this.outputElement.innerHTML = '';
        }
        this.setInputState(false);
        if (this.outputPoller) {
            clearInterval(this.outputPoller);
            this.outputPoller = null;
        }
        this.sessionId = null;
        this.inputQueue = [];
    }

    async startSession(code, language) {
        this.clear();
        if (!code?.trim()) {
            this.appendToConsole(this.lang === 'fr' ?
                "Erreur: Aucun code à exécuter\n" :
                "Error: No code to execute\n", 'error');
            return;
        }

        if (!this.csrfToken) {
            this.appendToConsole(this.lang === 'fr' ?
                'Erreur: Token CSRF non trouvé\n' :
                'Error: CSRF token not found\n', 'error');
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
            if (!data.success && data.error) {
                this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${data.error}\n`, 'error');
            }

            // Process next input in queue if any
            setTimeout(() => this.processInputQueue(), 100);
        } catch (error) {
            this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${error.message}\n`, 'error');
        }
    }

    startOutputPolling() {
        if (this.outputPoller) {
            clearInterval(this.outputPoller);
        }

        this.outputPoller = setInterval(async () => {
            if (!this.sessionId) {
                clearInterval(this.outputPoller);
                this.outputPoller = null;
                return;
            }

            try {
                const response = await fetch(`/activities/get_output?session_id=${this.sessionId}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                if (data.success) {
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
                    if (data.error) {
                        this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${data.error}\n`, 'error');
                    }
                    this.endSession();
                }
            } catch (error) {
                console.error('Error polling output:', error);
                this.endSession();
            }
        }, 100); // Poll every 100ms
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

    endSession() {
        if (this.sessionId) {
            if (this.csrfToken) {
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
            }

            if (this.outputPoller) {
                clearInterval(this.outputPoller);
                this.outputPoller = null;
            }

            this.sessionId = null;
            this.setInputState(false);
            this.inputQueue = [];
        }
    }
}

// Export for use in other files
window.InteractiveConsole = InteractiveConsole;