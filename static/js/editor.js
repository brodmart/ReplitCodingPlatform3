
// Editor execution logic
async function executeCode() {
    const output = document.getElementById('output');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const languageSelect = document.getElementById('languageSelect');
    
    if (!window.editor || !csrfToken) {
        console.error('Editor or CSRF token not available');
        return;
    }

    try {
        const response = await fetch('/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                code: window.editor.getValue(),
                language: languageSelect ? languageSelect.value : 'cpp'
            })
        });

        const result = await response.json();
        if (output) {
            output.innerHTML = `<pre class="${result.success ? 'success' : 'error'}">${result.output || result.error}</pre>`;
        }
    } catch (error) {
        if (output) {
            output.innerHTML = `<pre class="error">Erreur d'exécution: ${error.message}</pre>`;
        }
    }
}

// Set up event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const runButton = document.getElementById('runButton');
    const languageSelect = document.getElementById('languageSelect');

    if (runButton) {
        runButton.addEventListener('click', executeCode);
    }

    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            if (window.editor) {
                monaco.editor.setModelLanguage(window.editor.getModel(), this.value);
            }
        });
    }
});
