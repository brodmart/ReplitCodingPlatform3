/**
 * Interactive Console for handling program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        // Initialize with safer null checks and validation
        this.outputElement = options.outputElement;
        this.inputElement = options.inputElement;
        this.language = options.language || 'csharp';

        // Validate required elements immediately
        if (!this.outputElement || !(this.outputElement instanceof Element)) {
            throw new Error('Console requires a valid output element');
        }
        if (!this.inputElement || !(this.inputElement instanceof Element)) {
            throw new Error('Console requires a valid input element');
        }

        console.debug('Initializing console with:', {
            outputElement: this.outputElement.id,
            inputElement: this.inputElement.id,
            language: this.language
        });

        this.sessionId = null;
        this.isWaitingForInput = false;
        this.currentLanguage = this.language;
        this.compilationTimeout = 60000; // 60s timeout
        this.retryAttempts = 3;
        this.retryDelay = 1000;
        this.initialized = false;

        this.setupSocket();
        this.setupEventHandlers();
        this.clear();

        // Mark as initialized
        this.initialized = true;
        console.debug('Console initialization completed');
    }

    setupSocket() {
        this.socket = io({
            transports: ['websocket'],
            reconnection: true,
            reconnectionAttempts: this.retryAttempts,
            timeout: this.compilationTimeout,
            query: { client: 'web_console' }
        });

        this.socket.on('connect', () => {
            console.debug('Socket connected');
            this.appendSystemMessage('Connected to server');
        });

        this.socket.on('disconnect', () => {
            console.debug('Socket disconnected');
            this.appendSystemMessage('Disconnected from server');
            this.disableInput();
        });

        this.socket.on('error', (error) => {
            console.error('Socket error:', error);
            this.appendError(`Server error: ${error.message}`);
            if (!this.socket.connected) {
                this.disableInput();
            }
        });

        this.socket.on('connect_error', (error) => {
            console.error('Connection error:', error);
            this.appendError(`Connection error: ${error.message}`);
        });
    }

    setupEventHandlers() {
        // Console output handler
        this.socket.on('console_output', (data) => {
            console.debug('Received console output:', data);

            if (data.error) {
                this.appendError(data.error);
                return;
            }

            if (data.output) {
                this.appendOutput(data.output);
            }

            this.isWaitingForInput = data.waiting_for_input;
            this.updateInputState();
        });

        // Compilation result handler
        this.socket.on('compilation_result', (data) => {
            console.debug('Compilation result:', data);

            if (!data.success) {
                this.appendError(`Compilation failed: ${data.error}`);
                return;
            }

            if (data.session_id) {
                this.sessionId = data.session_id;
                this.appendSystemMessage('Program started successfully');

                if (data.interactive) {
                    this.isWaitingForInput = true;
                    this.updateInputState();
                }
            }
        });

        // Console input ready handler
        this.socket.on('console_input_ready', (data) => {
            console.debug('Input ready:', data);
            if (data.session_id === this.sessionId) {
                this.isWaitingForInput = true;
                this.updateInputState();
                if (data.prompt) {
                    this.appendOutput(data.prompt);
                }
            }
        });

        // Session end handler
        this.socket.on('console_session_ended', (data) => {
            console.debug('Session ended:', data);
            if (data.session_id === this.sessionId) {
                this.sessionId = null;
                this.isWaitingForInput = false;
                this.appendSystemMessage('Program execution completed');
                this.updateInputState();
            }
        });

        // Enhanced input handler with error handling
        this.inputElement.addEventListener('keydown', async (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                await this.handleInput();
            }
        });
    }

    async handleInput() {
        if (!this.isEnabled || !this.sessionId) {
            console.debug('Input handler: disabled or no session');
            return;
        }

        const input = this.inputElement.value.trim();
        if (!input) return;

        console.debug('Sending input:', input);
        this.inputElement.value = '';
        this.appendOutput(`> ${input}\n`, 'console-input');

        try {
            // Send input with acknowledgment
            await new Promise((resolve, reject) => {
                this.socket.emit('input', {
                    session_id: this.sessionId,
                    input: input + '\n'
                }, (response) => {
                    if (response && response.error) {
                        reject(new Error(response.error));
                    } else {
                        resolve();
                    }
                });

                setTimeout(() => reject(new Error('Input timeout')), 5000);
            });

            // Don't disable input immediately, wait for server confirmation
            console.debug('Input sent successfully');

        } catch (error) {
            console.error('Input error:', error);
            this.appendError(`Failed to send input: ${error.message}`);
            if (!this.socket.connected) {
                this.socket.connect();
            }
        }
    }

    appendOutput(text, className = '') {
        console.debug('Appending output:', { text, className });
        const line = document.createElement('div');
        line.className = `output-line ${className}`;
        line.textContent = text;
        this.outputElement.appendChild(line);
        this.scrollToBottom();
    }

    appendError(message) {
        console.error('Console error:', message);
        this.appendOutput(`Error: ${message}\n`, 'console-error');
    }

    appendSystemMessage(message) {
        console.debug('System message:', message);
        this.appendOutput(`System: ${message}\n`, 'console-system');
    }

    clear() {
        if (this.outputElement) {
            this.outputElement.innerHTML = '';
            this.sessionId = null;
            this.isWaitingForInput = false;
            this.updateInputState();
        }
    }

    scrollToBottom() {
        this.outputElement.scrollTop = this.outputElement.scrollHeight;
    }

    enableInput() {
        console.debug('Enabling input');
        this.isEnabled = true;
        this.inputElement.disabled = false;
        this.inputElement.placeholder = 'Enter input...';
        this.inputElement.focus();
    }

    disableInput() {
        console.debug('Disabling input');
        this.isEnabled = false;
        this.inputElement.disabled = true;
        this.inputElement.placeholder = 'Console inactive';
    }

    updateInputState() {
        console.debug('Updating input state:', {
            isWaitingForInput: this.isWaitingForInput,
            sessionId: this.sessionId
        });

        if (this.sessionId && this.isWaitingForInput) {
            this.enableInput();
        } else {
            this.disableInput();
        }
    }

    async compileAndRun(code) {
        console.debug('Compiling code:', {
            codeLength: code.length,
            language: this.currentLanguage
        });

        this.clear();
        this.appendSystemMessage('Compiling and running program...');

        try {
            await new Promise((resolve, reject) => {
                this.socket.emit('compile_and_run', {
                    code,
                    language: this.currentLanguage
                }, (response) => {
                    if (response && response.error) {
                        reject(new Error(response.error));
                    } else {
                        resolve(response);
                    }
                });

                setTimeout(() => reject(new Error('Compilation timeout')), this.compilationTimeout);
            });

        } catch (error) {
            console.error('Compilation error:', error);
            this.appendError(`Compilation failed: ${error.message}`);
            if (!this.socket.connected) {
                this.socket.connect();
            }
        }
    }
}

// Global initialization function with retry mechanism
function initializeConsole() {
    const language = document.getElementById('languageSelect')?.value || 'csharp';
    console.debug('Initializing console with language:', language);

    const consoleOutput = document.getElementById('consoleOutput');
    const consoleInput = document.getElementById('consoleInput');

    if (!window.consoleInitAttempts) {
        window.consoleInitAttempts = 0;
    }

    if (consoleOutput && consoleInput) {
        try {
            console.debug('Found required console elements');
            window.consoleInstance = new InteractiveConsole({
                outputElement: consoleOutput,
                inputElement: consoleInput,
                language: language
            });
            window.consoleInitAttempts = 0; // Reset counter on success
        } catch (error) {
            console.error('Failed to initialize console:', error);
            if (window.consoleInitAttempts < 10) {
                console.debug('Retrying initialization...');
                window.consoleInitAttempts++;
                // Exponential backoff for retries
                setTimeout(initializeConsole, Math.min(100 * Math.pow(2, window.consoleInitAttempts), 2000));
            } else {
                console.error('Max retries reached, console initialization failed');
            }
        }
    } else {
        console.error('Required console elements not found. Retrying...');
        if (window.consoleInitAttempts < 10) {
            window.consoleInitAttempts++;
            // Exponential backoff for retries
            setTimeout(initializeConsole, Math.min(100 * Math.pow(2, window.consoleInitAttempts), 2000));
        } else {
            console.error('Max retries reached, console initialization failed');
        }
    }
}

// Make sure the class is available globally
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}