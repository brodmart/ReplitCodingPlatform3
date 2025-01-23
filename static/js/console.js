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
        this.language = options.language || 'csharp';
        this.pendingOperations = new Map();

        // Defer initialization to ensure DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initializeAsync(options));
        } else {
            this.initializeAsync(options);
        }
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

            // Clear and show initializing message
            this.clear();
            this.appendSystemMessage('Initializing console...');

            // Initialize socket connection first
            await this.initializeSocket();

            // Setup event handlers after socket is ready
            this.setupEventHandlers();

            // Mark as initialized
            this.initialized = true;
            this.appendSystemMessage(`Console initialized for ${this.language} and ready`);
            console.debug('Console initialization completed successfully');

        } catch (error) {
            console.error('Failed to initialize console:', error);
            this.appendError(`Initialization failed: ${error.message}`);
            throw error; // Re-throw to allow proper error handling
        }
    }

    async waitForElements(options, timeout = 5000) {
        const startTime = Date.now();

        while (Date.now() - startTime < timeout) {
            // Check both direct options and DOM elements
            const outputElement = options.outputElement || document.getElementById('consoleOutput');
            const inputElement = options.inputElement || document.getElementById('consoleInput');

            if (outputElement instanceof Element && inputElement instanceof Element) {
                return { outputElement, inputElement };
            }

            // Wait before next check
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        throw new Error('Required console elements not found within timeout');
    }

    async initializeSocket() {
        return new Promise((resolve, reject) => {
            try {
                if (this.socket && this.socket.connected) {
                    this.socket.disconnect();
                }

                // Create new socket instance with error handling and timeouts
                this.socket = io({
                    transports: ['websocket'],
                    reconnection: true,
                    reconnectionAttempts: this.retryAttempts,
                    reconnectionDelay: this.retryDelay,
                    timeout: this.compilationTimeout
                });

                // Setup core event handlers
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

                // Set connection timeout
                const timeoutId = setTimeout(() => {
                    if (!this.socket.connected) {
                        const error = new Error('Socket connection timeout');
                        this.appendError(error.message);
                        reject(error);
                    }
                }, 5000);

                // Clear timeout on successful connection
                this.socket.once('connect', () => {
                    clearTimeout(timeoutId);
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
            console.debug('Received console output:', data);

            if (data.error) {
                this.appendError(data.error);
                return;
            }

            if (data.output) {
                this.appendOutput(data.output);
            }

            // Update input state based on server response
            this.isWaitingForInput = !!data.waiting_for_input;
            this.updateInputState();
        });

        this.socket.on('compilation_result', (data) => {
            if (!data) return;
            console.debug('Compilation result:', data);

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

        // Enhanced input handler with timeout and error handling
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
        this.disableInput(); // Disable input while processing

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