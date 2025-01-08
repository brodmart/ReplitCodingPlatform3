/**
 * Interactive Console class for handling real-time program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.consoleOutput = document.getElementById('consoleOutput');
        this.consoleInput = document.getElementById('consoleInput');
        this.sessionId = null;
        this.outputPoller = null;
        this.inputBuffer = [];
        this.isWaitingForInput = false;
        this.lang = options.lang || 'en';
        this.setupEventListeners();
    }

    setupEventListeners() {
        this.consoleInput.addEventListener('keypress', async (e) => {
            if (e.key === 'Enter') {
                const inputText = this.consoleInput.value;
                this.consoleInput.value = '';

                if (this.sessionId) {
                    await this.sendInput(inputText + '\n');
                }
            }
        });
    }

    appendToConsole(text, isInput = false) {
        // Create a text node to preserve whitespace and handle special characters
        const preElement = document.createElement('pre');
        preElement.style.margin = '0';
        preElement.style.fontFamily = 'inherit';

        if (isInput) {
            preElement.innerHTML = text;
            preElement.style.color = '#569cd6'; // Input text in blue
        } else {
            preElement.textContent = text;
            preElement.style.color = '#d4d4d4'; // Output text in default color
        }

        this.consoleOutput.appendChild(preElement);
        this.consoleOutput.scrollTop = this.consoleOutput.scrollHeight;
    }

    clear() {
        this.consoleOutput.innerHTML = '';
        this.inputBuffer = [];
        if (this.outputPoller) {
            clearInterval(this.outputPoller);
            this.outputPoller = null;
        }
        this.sessionId = null;
    }

    async startSession(code, language) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
        try {
            const response = await fetch('/activities/start_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify({
                    code: code,
                    language: language
                })
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
                this.appendToConsole(`Error: ${data.error || 'Failed to start session'}`);
                return false;
            }
        } catch (error) {
            this.appendToConsole(`Error: ${error.message}`);
            return false;
        }
    }

    async sendInput(input) {
        if (!this.sessionId) return;

        const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
        try {
            this.appendToConsole(input, true);

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
                this.appendToConsole(`Error: ${data.error}`);
            }
        } catch (error) {
            this.appendToConsole(`Error: ${error.message}`);
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
                if (data.success && data.output) {
                    this.appendToConsole(data.output);
                } else if (!data.success) {
                    clearInterval(this.outputPoller);
                    this.sessionId = null;
                }
            } catch (error) {
                console.error('Error polling output:', error);
                clearInterval(this.outputPoller);
                this.sessionId = null;
            }
        }, 100); // Poll every 100ms
    }

    async executeCode(code, language) {
        this.clear();
        if (!code.trim()) {
            this.appendToConsole(this.lang === 'fr' ? "Erreur: Aucun code à exécuter" : "Error: No code to execute");
            return;
        }

        this.appendToConsole(this.lang === 'fr' ? "Démarrage du programme...\n" : "Starting program...\n");

        // Start new session
        const success = await this.startSession(code, language);
        if (!success) {
            this.appendToConsole(this.lang === 'fr' ? "Échec du démarrage de la session" : "Failed to start session");
        }
    }

    endSession() {
        if (this.sessionId) {
            fetch('/activities/end_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            }).catch(console.error);

            this.sessionId = null;
            if (this.outputPoller) {
                clearInterval(this.outputPoller);
                this.outputPoller = null;
            }
        }
    }
}

// Export for use in other files
window.InteractiveConsole = InteractiveConsole;