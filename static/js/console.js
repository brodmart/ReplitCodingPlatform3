/**
 * Interactive Console class for handling real-time program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.outputElement = document.getElementById('consoleOutput');
        this.inputElement = document.getElementById('consoleInput');
        if (!this.outputElement || !this.inputElement) {
            console.error('Console elements not found');
            return;
        }
        this.sessionId = null;
        this.outputPoller = null;
        this.isWaitingForInput = false;
        this.lang = options.lang || 'en';
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Handle input submission
        this.inputElement.addEventListener('keypress', async (e) => {
            if (e.key === 'Enter' && this.isWaitingForInput) {
                e.preventDefault();
                const inputText = this.inputElement.value;
                this.inputElement.value = '';
                this.isWaitingForInput = false;

                // Display the input in the console with prompt
                this.appendToConsole(`> ${inputText}\n`, true);

                if (this.sessionId) {
                    await this.sendInput(inputText);
                }
            }
        });

        // Disable input when not waiting for it
        this.inputElement.addEventListener('focus', () => {
            if (!this.isWaitingForInput) {
                this.inputElement.blur();
            }
        });

        // Enable input when waiting
        this.inputElement.addEventListener('click', () => {
            if (this.isWaitingForInput) {
                this.inputElement.focus();
            }
        });
    }

    appendToConsole(text, isInput = false) {
        const line = document.createElement('div');
        line.className = isInput ? 'console-input' : 'console-output';
        line.textContent = text;
        this.outputElement.appendChild(line);
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    clear() {
        if (this.outputElement) {
            this.outputElement.innerHTML = '';
        }
        this.isWaitingForInput = false;
        if (this.outputPoller) {
            clearInterval(this.outputPoller);
            this.outputPoller = null;
        }
        this.sessionId = null;
        this.inputElement.value = '';
        this.inputElement.blur();
    }

    async startSession(code, language) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            this.appendToConsole(this.lang === 'fr' ? 
                'Erreur: Token CSRF non trouvé\n' : 
                'Error: CSRF token not found\n');
            return false;
        }

        try {
            const response = await fetch('/activities/start_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify({ code, language })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            if (data.success) {
                this.sessionId = data.session_id;
                this.startOutputPolling();
                return true;
            } else {
                this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${data.error || 'Failed to start session'}\n`);
                return false;
            }
        } catch (error) {
            this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${error.message}\n`);
            return false;
        }
    }

    async sendInput(input) {
        if (!this.sessionId) return;

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            this.appendToConsole(this.lang === 'fr' ? 
                'Erreur: Token CSRF non trouvé\n' : 
                'Error: CSRF token not found\n');
            return;
        }

        try {
            const response = await fetch('/activities/send_input', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    input: input
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            if (!data.success) {
                this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${data.error}\n`);
            }
        } catch (error) {
            this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${error.message}\n`);
        }
    }

    startOutputPolling() {
        if (this.outputPoller) {
            clearInterval(this.outputPoller);
        }

        this.outputPoller = setInterval(async () => {
            if (!this.sessionId) {
                clearInterval(this.outputPoller);
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

                    // Handle input state
                    if (data.waiting_for_input && !this.isWaitingForInput) {
                        this.isWaitingForInput = true;
                        this.inputElement.disabled = false;
                        this.inputElement.focus();
                    } else if (!data.waiting_for_input && this.isWaitingForInput) {
                        this.isWaitingForInput = false;
                        this.inputElement.disabled = true;
                        this.inputElement.blur();
                    }

                    if (data.session_ended) {
                        this.endSession();
                    }
                } else {
                    clearInterval(this.outputPoller);
                    this.sessionId = null;
                    if (data.error) {
                        this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${data.error}\n`);
                    }
                }
            } catch (error) {
                console.error('Error polling output:', error);
                clearInterval(this.outputPoller);
                this.sessionId = null;
                this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${error.message}\n`);
            }
        }, 100); // Poll every 100ms
    }

    async executeCode(code, language) {
        this.clear();
        if (!code?.trim()) {
            this.appendToConsole(this.lang === 'fr' ? 
                "Erreur: Aucun code à exécuter\n" : 
                "Error: No code to execute\n");
            return;
        }

        this.appendToConsole(this.lang === 'fr' ? 
            "Démarrage du programme...\n" : 
            "Starting program...\n");
        const success = await this.startSession(code, language);
        if (!success) {
            this.appendToConsole(this.lang === 'fr' ? 
                "Échec du démarrage de la session\n" : 
                "Failed to start session\n");
        }
    }

    endSession() {
        if (this.sessionId) {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
            if (csrfToken) {
                fetch('/activities/end_session', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify({
                        session_id: this.sessionId
                    })
                }).catch(console.error);
            }

            this.sessionId = null;
            this.isWaitingForInput = false;
            this.inputElement.disabled = true;
            this.inputElement.blur();

            if (this.outputPoller) {
                clearInterval(this.outputPoller);
                this.outputPoller = null;
            }
        }
    }
}

// Export for use in other files
window.InteractiveConsole = InteractiveConsole;