// Session management and timeout handling
class SessionHandler {
    constructor(options = {}) {
        this.timeoutWarning = options.timeoutWarning || 5 * 60 * 1000; // 5 minutes before timeout
        this.sessionTimeout = options.sessionTimeout || 30 * 60 * 1000; // 30 minutes total
        this.warningDisplayed = false;
        this.setupSessionHandling();
    }

    setupSessionHandling() {
        // Reset timer on user activity
        ['click', 'keypress', 'scroll', 'mousemove'].forEach(event => {
            document.addEventListener(event, () => this.resetTimer());
        });

        this.startTimer();
    }

    startTimer() {
        this.warningTimer = setTimeout(() => this.showWarning(), this.timeoutWarning);
        this.logoutTimer = setTimeout(() => this.handleTimeout(), this.sessionTimeout);
    }

    resetTimer() {
        clearTimeout(this.warningTimer);
        clearTimeout(this.logoutTimer);
        if (this.warningDisplayed) {
            this.hideWarning();
        }
        this.startTimer();
    }

    showWarning() {
        this.warningDisplayed = true;
        const warningDiv = document.createElement('div');
        warningDiv.className = 'alert alert-warning alert-dismissible fade show session-warning';
        warningDiv.setAttribute('role', 'alert');
        warningDiv.style.position = 'fixed';
        warningDiv.style.top = '20px';
        warningDiv.style.left = '50%';
        warningDiv.style.transform = 'translateX(-50%)';
        warningDiv.style.zIndex = '9999';
        warningDiv.innerHTML = `
            <strong>Attention!</strong> Votre session va expirer dans 5 minutes.
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            <div class="mt-2">
                <button onclick="sessionHandler.extendSession()" class="btn btn-sm btn-primary">
                    Prolonger la session
                </button>
            </div>
        `;
        document.body.appendChild(warningDiv);
    }

    hideWarning() {
        this.warningDisplayed = false;
        const warning = document.querySelector('.session-warning');
        if (warning) {
            warning.remove();
        }
    }

    async extendSession() {
        try {
            const response = await fetch('/extend-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                this.hideWarning();
                this.resetTimer();
                this.showNotification('success', 'Session prolongée avec succès!');
            } else {
                throw new Error('Failed to extend session');
            }
        } catch (error) {
            console.error('Session extension failed:', error);
            this.showNotification('error', 'Impossible de prolonger la session');
        }
    }

    handleTimeout() {
        window.location.href = '/logout';
    }

    showNotification(type, message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show notification-toast`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alertDiv);
        setTimeout(() => alertDiv.remove(), 5000);
    }
}

// Initialize session handler
window.sessionHandler = new SessionHandler();
