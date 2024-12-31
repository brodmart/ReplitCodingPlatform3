// Error boundary implementation for catching and handling JavaScript errors
class ErrorBoundary {
    constructor() {
        this.errorHandlers = [];
        this.setupGlobalHandlers();
    }

    setupGlobalHandlers() {
        // Handle uncaught exceptions
        window.onerror = (message, source, lineno, colno, error) => {
            this.handleError({
                type: 'uncaught_exception',
                message,
                source,
                lineno,
                colno,
                error: error?.stack || error?.message || error
            });
            return false;
        };

        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            this.handleError({
                type: 'unhandled_rejection',
                message: event.reason?.message || 'Unhandled Promise rejection',
                error: event.reason?.stack || event.reason
            });
        });

        // Handle network errors
        window.addEventListener('error', (event) => {
            if (event.target && (event.target.tagName === 'SCRIPT' || event.target.tagName === 'LINK')) {
                this.handleError({
                    type: 'resource_error',
                    message: `Failed to load resource: ${event.target.src || event.target.href}`,
                    source: event.target.src || event.target.href
                });
            }
        }, true);
    }

    handleError(error) {
        console.error('Application error:', error);
        
        // Show user-friendly error message
        const errorContainer = document.createElement('div');
        errorContainer.className = 'error-boundary-alert';
        errorContainer.innerHTML = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <strong>Une erreur est survenue</strong>
                <p>${this.formatErrorMessage(error)}</p>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;

        document.body.appendChild(errorContainer);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorContainer && errorContainer.parentNode) {
                errorContainer.parentNode.removeChild(errorContainer);
            }
        }, 5000);

        // Notify error handlers
        this.errorHandlers.forEach(handler => handler(error));
    }

    formatErrorMessage(error) {
        switch (error.type) {
            case 'resource_error':
                return 'Impossible de charger une ressource nécessaire. Veuillez rafraîchir la page.';
            case 'unhandled_rejection':
                return 'Une erreur inattendue est survenue. Veuillez réessayer.';
            default:
                return 'Une erreur est survenue lors de l\'exécution. Veuillez réessayer.';
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
