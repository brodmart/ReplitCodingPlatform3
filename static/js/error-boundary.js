// Error boundary implementation for catching and handling JavaScript errors
class ErrorBoundary {
    constructor() {
        this.errorHandlers = [];
        this.lastError = null;
        this.errorCount = 0;
        this.setupGlobalHandlers();
    }

    setupGlobalHandlers() {
        // Handle uncaught exceptions
        window.onerror = (message, source, lineno, colno, error) => {
            return this.handleError({
                type: 'uncaught_exception',
                message,
                source,
                lineno,
                colno,
                error: error?.stack || error?.message || error,
                timestamp: new Date().toISOString()
            });
        };

        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            this.handleError({
                type: 'unhandled_rejection',
                message: event.reason?.message || 'Unhandled Promise rejection',
                error: event.reason?.stack || event.reason,
                timestamp: new Date().toISOString()
            });
        });

        // Handle network errors
        window.addEventListener('error', (event) => {
            if (event.target && (event.target.tagName === 'SCRIPT' || event.target.tagName === 'LINK')) {
                this.handleError({
                    type: 'resource_error',
                    message: `Failed to load resource: ${event.target.src || event.target.href}`,
                    source: event.target.src || event.target.href,
                    timestamp: new Date().toISOString()
                });
            }
        }, true);

        // Add custom error handler for Monaco editor
        window.addEventListener('monaco-error', (event) => {
            this.handleError({
                type: 'editor_error',
                message: event.detail?.message || 'Editor error occurred',
                error: event.detail,
                timestamp: new Date().toISOString()
            });
        });
    }

    handleError(error) {
        console.error('Application error:', error);

        // Check for repeated errors
        const isRepeatedError = this.isRepeatedError(error);
        if (isRepeatedError) {
            this.errorCount++;
            if (this.errorCount > 3) {
                this.handleCriticalError();
                return true;
            }
        } else {
            this.errorCount = 1;
            this.lastError = error;
        }

        // Show user-friendly error message
        this.showErrorMessage(error);

        // Notify error handlers
        this.errorHandlers.forEach(handler => handler(error));

        // Log error to server
        this.logErrorToServer(error);

        return true; // Prevents the error from propagating
    }

    isRepeatedError(error) {
        if (!this.lastError) return false;
        return error.type === this.lastError.type && 
               error.message === this.lastError.message;
    }

    handleCriticalError() {
        const errorContainer = document.createElement('div');
        errorContainer.className = 'error-boundary-alert critical';
        errorContainer.innerHTML = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <strong>Erreur Critique</strong>
                <p>Des erreurs répétées ont été détectées. La page va être rechargée pour résoudre le problème.</p>
            </div>
        `;
        document.body.appendChild(errorContainer);

        // Force reload after 3 seconds
        setTimeout(() => {
            window.location.reload();
        }, 3000);
    }

    showErrorMessage(error) {
        const errorContainer = document.createElement('div');
        errorContainer.className = 'error-boundary-alert';
        errorContainer.innerHTML = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <strong>${this.getErrorTitle(error)}</strong>
                <p>${this.formatErrorMessage(error)}</p>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                ${this.getErrorAction(error)}
            </div>
        `;

        document.body.appendChild(errorContainer);

        // Auto-remove after 5 seconds unless it's critical
        if (error.type !== 'critical') {
            setTimeout(() => {
                if (errorContainer && errorContainer.parentNode) {
                    errorContainer.parentNode.removeChild(errorContainer);
                }
            }, 5000);
        }
    }

    getErrorTitle(error) {
        switch (error.type) {
            case 'resource_error':
                return 'Erreur de Chargement';
            case 'editor_error':
                return 'Erreur de l\'Éditeur';
            case 'critical':
                return 'Erreur Critique';
            default:
                return 'Erreur Système';
        }
    }

    formatErrorMessage(error) {
        switch (error.type) {
            case 'resource_error':
                return 'Impossible de charger une ressource nécessaire. Veuillez rafraîchir la page.';
            case 'editor_error':
                return 'L\'éditeur a rencontré une erreur. Vos modifications ont été sauvegardées.';
            case 'unhandled_rejection':
                return 'Une erreur inattendue est survenue. Vos données sont sauvegardées.';
            default:
                return 'Une erreur est survenue. Veuillez réessayer.';
        }
    }

    getErrorAction(error) {
        switch (error.type) {
            case 'resource_error':
                return `<div class="mt-2">
                    <button onclick="window.location.reload()" class="btn btn-sm btn-primary">
                        Rafraîchir la page
                    </button>
                </div>`;
            case 'editor_error':
                return `<div class="mt-2">
                    <button onclick="window.dispatchEvent(new CustomEvent('retry-editor'))" class="btn btn-sm btn-primary">
                        Réessayer
                    </button>
                </div>`;
            default:
                return '';
        }
    }

    async logErrorToServer(error) {
        try {
            await fetch('/log-error', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    type: error.type,
                    message: error.message,
                    stack: error.error,
                    timestamp: error.timestamp,
                    url: window.location.href
                })
            });
        } catch (e) {
            console.error('Failed to log error to server:', e);
        }
    }

    addErrorHandler(handler) {
        if (typeof handler === 'function') {
            this.errorHandlers.push(handler);
        }
    }
}

// Initialize error boundary
window.errorBoundary = new ErrorBoundary();