/**
 * Interactive Console for handling program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        // Initialize with safer null checks
        this.outputElement = options.outputElement;
        this.inputElement = options.inputElement;
        this.language = options.language || 'csharp';

        console.debug('Attempting console initialization with:', {
            outputElement: !!this.outputElement,
            inputElement: !!this.inputElement,
            language: this.language
        });

        if (!this.outputElement || !this.inputElement) {
            console.error('Console initialization failed: Missing required elements');
            throw new Error('Console requires valid output and input elements');
        }

        this.sessionId = null;
        this.isWaitingForInput = false;
        this.currentLanguage = this.language;
        this.compilationTimeout = 60000; // 60s timeout
        this.retryAttempts = 3;
        this.retryDelay = 1000;

        console.debug('Interactive Console initialized with language:', this.currentLanguage);

        this.setupSocket();
        this.setupEventHandlers();
        this.clear();
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
            // Only disable input on fatal errors
            if (!this.socket.connected) {
                this.disableInput();
            }
        });

        // Enhanced error handling
        this.socket.on('connect_error', (error) => {
            console.error('Connection error:', error);
            this.appendError(`Connection error: ${error.message}`);
        });
    }

    setupEventHandlers() {
        // Handle program output
        this.socket.on('output', (data) => {
            console.debug('Received output:', data);

            if (data.error) {
                this.appendError(data.error);
                return;
            }

            if (data.output) {
                this.appendOutput(data.output);
            }

            // Update input state based on server's indication
            this.isWaitingForInput = data.waiting_for_input;
            this.updateInputState();
        });

        // Handle compilation results
        this.socket.on('compilation_result', (data) => {
            console.debug('Compilation result:', data);

            if (!data.success) {
                this.appendError(`Compilation failed: ${data.error}`);
                return;
            }

            if (data.session_id) {
                this.sessionId = data.session_id;
                this.appendSystemMessage('Program started successfully');

                // Enable input for interactive sessions
                if (data.interactive) {
                    this.isWaitingForInput = true;
                    this.updateInputState();
                }
            }
        });

        // Handle console input ready state
        this.socket.on('console_input_ready', (data) => {
            console.debug('Input ready:', data);
            if (data.session_id === this.sessionId) {
                this.isWaitingForInput = true;
                this.updateInputState();
            }
        });

        // Handle session end
        this.socket.on('console_session_ended', (data) => {
            console.debug('Session ended:', data);
            if (data.session_id === this.sessionId) {
                this.sessionId = null;
                this.isWaitingForInput = false;
                this.appendSystemMessage('Program execution completed');
                this.updateInputState();
            }
        });

        // Input handler with improved error handling
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
            // Emit input event and wait for acknowledgment
            await new Promise((resolve, reject) => {
                this.socket.emit('input', {
                    session_id: this.sessionId,
                    input: input + '\n'  // Add newline for proper input handling
                }, (response) => {
                    if (response && response.error) {
                        reject(new Error(response.error));
                    } else {
                        resolve();
                    }
                });

                // Set timeout for acknowledgment
                setTimeout(() => reject(new Error('Input timeout')), 5000);
            });

            this.isWaitingForInput = false;
            this.updateInputState();

        } catch (error) {
            console.error('Input error:', error);
            this.appendError(`Failed to send input: ${error.message}`);
            // Retry connection if needed
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

                // Set compilation timeout
                setTimeout(() => reject(new Error('Compilation timeout')), this.compilationTimeout);
            });

        } catch (error) {
            console.error('Compilation error:', error);
            this.appendError(`Compilation failed: ${error.message}`);
            // Retry connection if needed
            if (!this.socket.connected) {
                this.socket.connect();
            }
        }
    }
}

// Make sure the class is available globally
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}