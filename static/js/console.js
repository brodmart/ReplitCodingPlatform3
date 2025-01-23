/**
 * Interactive Console for handling program I/O
 */
class InteractiveConsole {
    constructor(options = {}) {
        // Initialize state
        this.initialized = false;
        this.sessionId = null;
        this.isWaitingForInput = false;
        this.compilationTimeout = 60000; // 60s timeout
        this.retryAttempts = 3;
        this.retryDelay = 1000;
        this.socket = null;

        // Immediate initialization with proper error handling
        this.initializeAsync(options).catch(error => {
            console.error('Failed to initialize console:', error);
            if (options.outputElement) {
                this.appendError(`Initialization failed: ${error.message}`);
            }
        });
    }

    async initializeAsync(options) {
        try {
            if (!options || typeof options !== 'object') {
                throw new Error('Invalid console options');
            }

            // Wait for elements with timeout
            const elements = await this.waitForElements(options);
            this.outputElement = elements.outputElement;
            this.inputElement = elements.inputElement;
            this.language = options.language || 'csharp';

            // Initialize socket connection
            await this.initializeSocket();

            // Setup event handlers
            this.setupEventHandlers();

            // Clear and mark as initialized
            this.clear();
            this.initialized = true;

            // Success message
            this.appendSystemMessage('Console initialized and ready');
            console.debug('Console initialization completed successfully');

        } catch (error) {
            console.error('Console initialization failed:', error);
            throw error;
        }
    }

    async waitForElements(options, timeout = 5000) {
        const startTime = Date.now();
        const checkElements = () => {
            const outputElement = options.outputElement || document.getElementById('consoleOutput');
            const inputElement = options.inputElement || document.getElementById('consoleInput');

            if (outputElement instanceof Element && inputElement instanceof Element) {
                return { outputElement, inputElement };
            }
            return null;
        };

        while (Date.now() - startTime < timeout) {
            const elements = checkElements();
            if (elements) {
                return elements;
            }
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        throw new Error('Required console elements not found within timeout');
    }

    async initializeSocket() {
        return new Promise((resolve, reject) => {
            try {
                this.socket = io({
                    transports: ['websocket'],
                    reconnection: true,
                    reconnectionAttempts: this.retryAttempts,
                    timeout: this.compilationTimeout,
                    query: { client: 'web_console' }
                });

                this.socket.on('connect', () => {
                    console.debug('Socket connected successfully');
                    this.appendSystemMessage('Connected to server');
                    resolve();
                });

                this.socket.on('connect_error', (error) => {
                    console.error('Socket connection error:', error);
                    this.appendError(`Connection error: ${error.message}`);
                    reject(error);
                });

                // Set timeout for socket connection
                setTimeout(() => {
                    if (!this.socket.connected) {
                        reject(new Error('Socket connection timeout'));
                    }
                }, 5000);

            } catch (error) {
                reject(error);
            }
        });
    }

    setupEventHandlers() {
        if (!this.socket) {
            throw new Error('Socket not initialized');
        }

        this.socket.on('disconnect', () => {
            console.debug('Socket disconnected');
            this.appendSystemMessage('Disconnected from server');
            this.disableInput();
        });

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

        // Enhanced input handler
        if (this.inputElement) {
            this.inputElement.addEventListener('keydown', async (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    await this.handleInput();
                }
            });
        }
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
        if (!this.outputElement) return;

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
        if (this.outputElement) {
            this.outputElement.scrollTop = this.outputElement.scrollHeight;
        }
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
        if (!this.initialized) {
            throw new Error('Console not initialized');
        }

        console.debug('Compiling code:', {
            codeLength: code.length,
            language: this.language
        });

        this.clear();
        this.appendSystemMessage('Compiling and running program...');

        try {
            await new Promise((resolve, reject) => {
                this.socket.emit('compile_and_run', {
                    code,
                    language: this.language
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

// Export for global access
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}

// Ensure initialization happens after DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const outputElement = document.getElementById('consoleOutput');
    const inputElement = document.getElementById('consoleInput');
    const language = document.getElementById('languageSelect')?.value || 'csharp';

    if (outputElement && inputElement) {
        window.consoleInstance = new InteractiveConsole({
            outputElement,
            inputElement,
            language
        });
    }
});