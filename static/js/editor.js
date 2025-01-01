// Editor initialization
let editor = null;

document.addEventListener('DOMContentLoaded', function() {
    initializeEditor();
});

function initializeEditor() {
    try {
        const editorElement = document.getElementById('editor');
        if (!editorElement) {
            console.error('Editor element not found');
            return;
        }

        // Initialize CodeMirror
        editor = CodeMirror.fromTextArea(editorElement, {
            mode: 'text/x-c++src', // Default to C++
            theme: 'dracula',
            lineNumbers: true,
            matchBrackets: true,
            autoCloseBrackets: true,
            indentUnit: 4,
            tabSize: 4,
            indentWithTabs: true,
            lineWrapping: true,
            viewportMargin: Infinity,
            extraKeys: {
                "Tab": "indentMore",
                "Shift-Tab": "indentLess"
            }
        });

        // Set initial value from textarea
        const initialValue = editorElement.value;
        if (initialValue) {
            editor.setValue(initialValue);
        }

        // Language switching with proper mode updating
        const languageSelect = document.getElementById('languageSelect');
        if (languageSelect) {
            // Set initial mode based on selected language
            const initialMode = languageSelect.value === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
            editor.setOption('mode', initialMode);

            languageSelect.addEventListener('change', function() {
                const mode = this.value === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
                editor.setOption('mode', mode);
                console.log('Language switched to:', this.value, 'with mode:', mode);
            });
        }

        setupRunButton();
        editor.refresh();
        console.log('Editor initialized successfully');
    } catch (error) {
        console.error('Editor initialization failed:', error);
        handleEditorError();
    }
}

function setupRunButton() {
    const runButton = document.getElementById('runButton');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const outputDiv = document.getElementById('output');

    if (!runButton || !outputDiv) {
        console.error('Required elements not found');
        return;
    }

    runButton.addEventListener('click', async function() {
        if (!editor) {
            outputDiv.innerHTML = '<div class="error">Editor not initialized</div>';
            return;
        }

        const code = editor.getValue();
        const language = document.getElementById('languageSelect')?.value || 'cpp';
        console.log('Executing code with language:', language);

        if (!code.trim()) {
            outputDiv.innerHTML = '<div class="error">Le code ne peut pas être vide</div>';
            return;
        }

        // Show loading state
        if (loadingOverlay) loadingOverlay.style.display = 'flex';
        outputDiv.innerHTML = '<div class="text-muted">Exécution en cours...</div>';

        try {
            const activityId = window.location.pathname.match(/\/activity\/(\d+)/)?.[1];
            const endpoint = activityId ? `/activities/activity/${activityId}/submit` : '/execute';

            // Get CSRF token with error handling
            const csrfTokenElement = document.querySelector('input[name="csrf_token"]');
            if (!csrfTokenElement) {
                throw new Error('CSRF token not found. Please refresh the page.');
            }
            const csrfToken = csrfTokenElement.value;

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ 
                    code, 
                    language // Always send the current language selection
                }),
                credentials: 'same-origin'
            });

            let data;
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                throw new Error('Server returned non-JSON response');
            }

            if (!response.ok) {
                throw new Error(data.error || 'Error executing code');
            }

            if (data.error) {
                outputDiv.innerHTML = `<pre class="error"><span class="error-badge">Error</span>${data.error.trim()}</pre>`;
            } else {
                outputDiv.innerHTML = `<pre class="output-success">${(data.output || 'No output').trim()}</pre>`;
            }
        } catch (error) {
            console.error('Execution error:', error);
            outputDiv.innerHTML = `<pre class="error">${error.message || 'Error executing code'}</pre>`;
        } finally {
            // Hide loading overlay
            if (loadingOverlay) loadingOverlay.style.display = 'none';
        }
    });
}

function handleEditorError() {
    const editorElement = document.getElementById('editor');
    const outputDiv = document.getElementById('output');

    if (editorElement) {
        editorElement.style.display = 'none';
    }
    if (outputDiv) {
        outputDiv.innerHTML = `
            <div class="alert alert-danger">
                Failed to initialize code editor. Please refresh the page or contact support if the issue persists.
            </div>
        `;
    }
}