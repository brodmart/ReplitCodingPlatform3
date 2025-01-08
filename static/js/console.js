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
        this.inputQueue = [];
        this.setupEventListeners();
        this.csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!this.csrfToken) {
            console.error('CSRF token not found');
        }
    }

    setupEventListeners() {
        // Handle input submission
        this.inputElement.addEventListener('keypress', async (e) => {
            if (e.key === 'Enter' && this.isWaitingForInput) {
                e.preventDefault();
                const inputText = this.inputElement.value;
                this.inputElement.value = '';
                this.isWaitingForInput = false;
                this.inputElement.disabled = true;

                // Display the input in the console
                this.appendToConsole(`> ${inputText}\n`, 'input');

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

        // Handle paste events
        this.inputElement.addEventListener('paste', (e) => {
            if (this.isWaitingForInput) {
                e.preventDefault();
                const pastedText = e.clipboardData.getData('text');
                const lines = pastedText.split('\n');

                if (lines.length > 1) {
                    // Queue multiple lines of input
                    this.inputQueue.push(...lines.filter(line => line.trim()));
                    this.processInputQueue();
                } else {
                    this.inputElement.value = pastedText;
                }
            }
        });
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

        // Apply syntax highlighting for code-like content
        if (type === 'output') {
            text = this.highlightSyntax(text);
        }

        line.innerHTML = text;
        this.outputElement.appendChild(line);
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    highlightSyntax(text) {
        // Basic syntax highlighting for common programming elements
        return text
            .replace(/\b(if|else|while|for|return|int|string|bool|void|class|public|private)\b/g, '<span class="console-keyword">$1</span>')
            .replace(/"([^"\\]*(\\.[^"\\]*)*)"/g, '<span class="console-string">$&</span>')
            .replace(/\b(\d+)\b/g, '<span class="console-number">$1</span>')
            .replace(/\/\/.*/g, '<span class="console-comment">$&</span>');
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
        this.inputElement.disabled = true;
        this.inputQueue = [];
        this.inputElement.blur();
    }

    async startSession(code, language) {
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
            if (response.ok) {
                if (data.success) {
                    this.sessionId = data.session_id;
                    this.startOutputPolling();
                    return true;
                } else {
                    this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${data.error || 'Failed to start session'}\n`, 'error');
                    return false;
                }
            } else {
                this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${data.error || `HTTP error! status: ${response.status}`}\n`, 'error');
                return false;
            }
        } catch (error) {
            this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${error.message}\n`, 'error');
            return false;
        }
    }

    async sendInput(input) {
        if (!this.sessionId) return;

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            this.appendToConsole(this.lang === 'fr' ?
                'Erreur: Token CSRF non trouvé\n' :
                'Error: CSRF token not found\n', 'error');
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
                    const wasWaiting = this.isWaitingForInput;
                    this.isWaitingForInput = data.waiting_for_input;

                    // Update UI for input state
                    this.inputElement.disabled = !this.isWaitingForInput;
                    const inputLine = document.querySelector('.console-input-line');
                    if (this.isWaitingForInput) {
                        inputLine?.classList.add('console-waiting');
                        if (!wasWaiting) {
                            // Only focus and process queue when transitioning to waiting state
                            this.inputElement.focus();
                            this.processInputQueue();
                        }
                    } else {
                        inputLine?.classList.remove('console-waiting');
                        this.inputElement.blur();
                    }

                    if (data.session_ended) {
                        this.endSession();
                    }
                } else {
                    clearInterval(this.outputPoller);
                    this.sessionId = null;
                    if (data.error) {
                        this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${data.error}\n`, 'error');
                    }
                }
            } catch (error) {
                console.error('Error polling output:', error);
                clearInterval(this.outputPoller);
                this.sessionId = null;
                this.appendToConsole(`${this.lang === 'fr' ? 'Erreur: ' : 'Error: '}${error.message}\n`, 'error');
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
            this.inputQueue = [];

            const inputLine = document.querySelector('.console-input-line');
            inputLine?.classList.remove('console-waiting');

            if (this.outputPoller) {
                clearInterval(this.outputPoller);
                this.outputPoller = null;
            }
        }
    }
}

// Export for use in other files
window.InteractiveConsole = InteractiveConsole;