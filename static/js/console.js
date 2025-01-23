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
        this.retryDelay = 2000;
        this.socket = null;
        this.language = options.language || 'csharp';
        this.pendingOperations = new Map();
        this.initializationAttempts = 0;
        this.maxInitializationAttempts = 3;
        this.elementWaitTimeout = 20000;

        // Start initialization
        this.initWithRetry(options);
    }

    initWithRetry(options) {
        console.debug('Starting console initialization');

        const initConsole = () => {
            // Check if elements exist first
            const outputElement = document.getElementById('consoleOutput');
            const inputElement = document.getElementById('consoleInput');

            if (!outputElement || !inputElement) {
                this.initializationAttempts++;
                console.debug(`Elements not found, attempt ${this.initializationAttempts}`);

                if (this.initializationAttempts < this.maxInitializationAttempts) {
                    setTimeout(() => initConsole(), this.retryDelay);
                } else {
                    console.error('Max initialization attempts reached');
                    if (outputElement) {
                        outputElement.innerHTML = '<div class="console-error">Failed to initialize console after multiple attempts</div>';
                    }
                }
                return;
            }

            // Store elements
            this.outputElement = outputElement;
            this.inputElement = inputElement;

            // Initialize socket and setup handlers
            this.initializeSocketAndHandlers()
                .then(() => {
                    this.initialized = true;
                    this.appendSystemMessage('Console initialized successfully');
                    console.debug('Console initialization completed');
                })
                .catch(error => {
                    console.error('Socket initialization failed:', error);
                    this.appendError(`Initialization failed: ${error.message}`);

                    // Retry socket initialization
                    if (this.initializationAttempts < this.maxInitializationAttempts) {
                        this.initializationAttempts++;
                        setTimeout(() => this.initializeSocketAndHandlers(), this.retryDelay);
                    }
                });
        };

        // Start initialization process
        initConsole();
    }

    async initializeSocketAndHandlers() {
        if (!this.outputElement) {
            throw new Error('Console not properly initialized');
        }

        // Clear and show initializing message
        this.clear();
        this.appendSystemMessage('Initializing console...');

        // Initialize socket connection
        await this.initializeSocket();

        // Setup event handlers
        this.setupEventHandlers();
    }

    async initializeSocket() {
        return new Promise((resolve, reject) => {
            try {
                if (this.socket && this.socket.connected) {
                    this.socket.disconnect();
                }

                this.socket = io({
                    transports: ['websocket'],
                    reconnection: true,
                    reconnectionAttempts: this.retryAttempts,
                    reconnectionDelay: this.retryDelay,
                    timeout: this.compilationTimeout
                });

                const connectionTimeout = setTimeout(() => {
                    if (!this.socket.connected) {
                        reject(new Error('Socket connection timeout'));
                    }
                }, 5000);

                this.socket.on('connect', () => {
                    clearTimeout(connectionTimeout);
                    console.debug('Socket connected successfully');
                    this.appendSystemMessage('Connected to server');
                    resolve();
                });

                this.socket.on('connect_error', (error) => {
                    clearTimeout(connectionTimeout);
                    console.error('Socket connection error:', error);
                    this.appendError(`Connection error: ${error.message}`);
                    reject(error);
                });

            } catch (error) {
                this.appendError(`Socket initialization failed: ${error.message}`);
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
            if (!data) return;

            if (data.error) {
                this.appendError(data.error);
                return;
            }

            if (data.output) {
                this.appendOutput(data.output);
            }

            this.isWaitingForInput = !!data.waiting_for_input;
            this.updateInputState();
        });

        this.socket.on('compilation_result', (data) => {
            if (!data) return;

            if (!data.success) {
                this.appendError(`Compilation failed: ${data.error}`);
                return;
            }

            if (data.session_id) {
                this.sessionId = data.session_id;
                this.appendSystemMessage(`${this.language} program started successfully`);

                if (data.interactive) {
                    this.isWaitingForInput = true;
                    this.updateInputState();
                }
            }
        });

        if (this.inputElement) {
            this.inputElement.addEventListener('keydown', async (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    await this.handleInput().catch(error => {
                        console.error('Input handling error:', error);
                        this.appendError(`Input error: ${error.message}`);
                    });
                }
            });
        }
    }

    appendOutput(text, className = '') {
        if (!this.outputElement) return;

        const line = document.createElement('div');
        line.className = `output-line ${className}`;
        line.textContent = text;
        this.outputElement.appendChild(line);
        this.scrollToBottom();
    }

    appendError(message) {
        console.error('Console error:', message);
        this.appendOutput(`Error: ${message}`, 'console-error');
    }

    appendSystemMessage(message) {
        console.debug('System message:', message);
        this.appendOutput(`System: ${message}`, 'console-system');
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
        if (!this.inputElement) return;
        this.inputElement.disabled = false;
        this.inputElement.placeholder = 'Enter input...';
        this.inputElement.focus();
    }

    disableInput() {
        if (!this.inputElement) return;
        this.inputElement.disabled = true;
        this.inputElement.placeholder = 'Console inactive';
    }

    updateInputState() {
        if (this.sessionId && this.isWaitingForInput) {
            this.enableInput();
        } else {
            this.disableInput();
        }
    }

    async handleInput() {
        if (!this.inputElement || !this.sessionId) {
            throw new Error('Console not ready for input');
        }

        const input = this.inputElement.value.trim();
        if (!input) return;

        this.inputElement.value = '';
        this.appendOutput(`> ${input}`, 'console-input');
        this.disableInput();

        try {
            await new Promise((resolve, reject) => {
                const timeoutId = setTimeout(() => {
                    reject(new Error('Input timeout'));
                }, 5000);

                if (!this.socket.connected) {
                    clearTimeout(timeoutId);
                    reject(new Error('Socket disconnected'));
                    return;
                }

                this.socket.emit('input', {
                    session_id: this.sessionId,
                    input: input + '\n',
                    language: this.language
                }, (response) => {
                    clearTimeout(timeoutId);
                    if (response && response.error) {
                        reject(new Error(response.error));
                    } else {
                        resolve();
                    }
                });
            });

        } catch (error) {
            console.error('Input error:', error);
            this.appendError(`Failed to send input: ${error.message}`);
            throw error;
        } finally {
            this.updateInputState();
        }
    }
}

// Export for global access
if (typeof window !== 'undefined') {
    window.InteractiveConsole = InteractiveConsole;
}

// Ensure proper cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.consoleInstance && window.consoleInstance.socket) {
        window.consoleInstance.socket.disconnect();
    }
});