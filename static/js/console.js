/**
 * Shared interactive console functionality for code execution
 */
class InteractiveConsole {
    constructor(options = {}) {
        this.consoleOutput = document.getElementById('consoleOutput');
        this.consoleInput = document.getElementById('consoleInput');
        this.inputBuffer = [];
        this.inputCallback = null;
        this.lang = options.lang || 'en';
        this.setupEventListeners();
    }

    setupEventListeners() {
        this.consoleInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const inputText = this.consoleInput.value;
                this.appendToConsole(inputText, true);
                this.inputBuffer.push(inputText);
                this.consoleInput.value = '';

                if (this.inputCallback) {
                    this.inputCallback(inputText);
                    this.inputCallback = null;
                }
            }
        });
    }

    appendToConsole(text, isInput = false) {
        const line = document.createElement('div');
        line.className = isInput ? 'console-input-line' : '';
        
        if (isInput) {
            line.innerHTML = `<span class="console-prompt">&gt;</span> ${text}`;
        } else {
            line.textContent = text;
        }
        
        this.consoleOutput.appendChild(line);
        this.consoleOutput.scrollTop = this.consoleOutput.scrollHeight;
    }

    clear() {
        this.consoleOutput.innerHTML = '';
        this.inputBuffer = [];
    }

    async executeCode(code, language) {
        this.clear();
        
        const csrfToken = document.querySelector('input[name="csrf_token"]').value;
        if (!code.trim()) {
            this.appendToConsole(this.lang === 'fr' ? "Erreur: Aucun code à exécuter" : "Error: No code to execute");
            return;
        }

        try {
            this.appendToConsole(this.lang === 'fr' ? "Exécution du programme...\n" : "Running program...\n");

            const response = await fetch('/activities/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify({
                    code: code,
                    language: language,
                    input: this.inputBuffer.join('\n')
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                if (data.output) {
                    this.appendToConsole(data.output);
                }
                if (data.error) {
                    this.appendToConsole(`\n${this.lang === 'fr' ? 'Avertissement' : 'Warning'}: ${data.error}`);
                }
            } else {
                this.appendToConsole(`${this.lang === 'fr' ? 'Erreur' : 'Error'}: ${data.error || (this.lang === 'fr' ? 'Une erreur inconnue est survenue' : 'Unknown error occurred')}`);
            }
        } catch (error) {
            console.error('Execution error:', error);
            this.appendToConsole(`${this.lang === 'fr' ? 'Erreur' : 'Error'}: ${error.message}`);
        }
    }
}

// Export for use in other files
window.InteractiveConsole = InteractiveConsole;
