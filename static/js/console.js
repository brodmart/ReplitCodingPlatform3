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
        this.retryAttempts = 5;  // Increased from 3 to 5
        this.retryDelay = 3000;  // Increased from 2000 to 3000ms
        this.socketConnectionTimeout = 10000; // 10s socket connection timeout
        this.socket = null;
        this.language = options.language || 'csharp';
        this.pendingOperations = new Map();
        this.initializationAttempts = 0;
        this.maxInitializationAttempts = 5;  // Maximum number of retries
        this.elementWaitTimeout = 30000;  // 30s timeout for element detection

        // Add compilation methods
        this.compileAndRun = async (code) => {
            if (!this.initialized) {
                throw new Error('Console not fully initialized');
            }
            if (!this.socket?.connected) {
                await this.reconnectSocket();
            }

            // Clear previous output
            this.clear();
            this.appendSystemMessage('Compiling and running code...');

            return new Promise((resolve, reject) => {
                const timeoutId = setTimeout(() => {
                    reject(new Error('Compilation timeout'));
                }, this.compilationTimeout);

                this.socket.emit('compile_and_run', {
                    code: code,
                    language: this.language
                }, (response) => {
                    clearTimeout(timeoutId);
                    if (response?.error) {
                        this.appendError(`Compilation failed: ${response.error}`);
                        reject(new Error(response.error));
                    } else {
                        this.sessionId = response.session_id;
                        this.isWaitingForInput = response.interactive || false;
                        this.updateInputState();
                        resolve(response);
                    }
                });
            });
        };

        // Start initialization
        this.initWithRetry(options);
    }

    async reconnectSocket() {
        if (this.socket?.connected) return;

        let attempts = 0;
        const maxAttempts = 3;

        while (attempts < maxAttempts) {
            try {
                await this.initializeSocket();
                return;
            } catch (error) {
                attempts++;
                if (attempts === maxAttempts) {
                    throw new Error('Failed to reconnect socket after multiple attempts');
                }
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }
    }

    async initWithRetry(options) {
        console.debug('Starting console initialization');

        const waitForElements = async () => {
            const startTime = Date.now();

            while (Date.now() - startTime < this.elementWaitTimeout) {
                const outputElement = document.getElementById('consoleOutput');
                const inputElement = document.getElementById('consoleInput');

                if (outputElement && inputElement) {
                    return { outputElement, inputElement };
                }

                await new Promise(resolve => setTimeout(resolve, 500));
            }

            throw new Error('Timeout waiting for console elements');
        };

        const initConsole = async () => {
            try {
                // Wait for elements with timeout
                const { outputElement, inputElement } = await waitForElements();

                // Store elements
                this.outputElement = outputElement;
                this.inputElement = inputElement;

                // Initialize socket and setup handlers
                await this.initializeSocketAndHandlers();

                this.initialized = true;
                this.appendSystemMessage('Console initialized successfully');
                console.debug('Console initialization completed');

            } catch (error) {
                this.initializationAttempts++;
                console.warn(`Console initialization attempt ${this.initializationAttempts} failed:`, error);

                if (this.outputElement) {
                    this.outputElement.innerHTML = `<div class="console-error">Initialization attempt ${this.initializationAttempts} failed: ${error.message}</div>`;
                }

                if (this.initializationAttempts < this.maxInitializationAttempts) {
                    console.debug(`Retrying initialization in ${this.retryDelay}ms`);
                    await new Promise(resolve => setTimeout(resolve, this.retryDelay));
                    await initConsole();
                } else {
                    console.error('Max initialization attempts reached');
                    if (this.outputElement) {
                        this.outputElement.innerHTML = '<div class="console-error">Failed to initialize console after multiple attempts. Please refresh the page.</div>';
                    }
                    throw new Error('Failed to initialize console after multiple attempts');
                }
            }
        };

        // Start initialization process
        try {
            await initConsole();
        } catch (error) {
            console.error('Console initialization failed:', error);
            this.appendError(`Initialization failed: ${error.message}`);
        }
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
                if (this.socket?.connected) {
                    this.socket.disconnect();
                }

                this.socket = io({
                    transports: ['websocket'],
                    reconnection: true,
                    reconnectionAttempts: this.retryAttempts,
                    reconnectionDelay: this.retryDelay,
                    timeout: this.socketConnectionTimeout
                });

                const connectionTimeout = setTimeout(() => {
                    if (!this.socket?.connected) {
                        reject(new Error('Socket connection timeout'));
                    }
                }, this.socketConnectionTimeout);

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
                this.appendSystemMessage(`Program started successfully`);

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
                    try {
                        await this.handleInput();
                    } catch (error) {
                        console.error('Input handling error:', error);
                        this.appendError(`Input error: ${error.message}`);
                    }
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
    if (window.consoleInstance?.socket) {
        window.consoleInstance.socket.disconnect();
    }
});