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
            mode: 'text/x-c++src',
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

        // Language switching
        const languageSelect = document.getElementById('languageSelect');
        if (languageSelect) {
            languageSelect.addEventListener('change', function() {
                const mode = this.value === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
                editor.setOption('mode', mode);
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

        if (!code.trim()) {
            outputDiv.innerHTML = '<div class="error">Le code ne peut pas être vide</div>';
            return;
        }

        // Show loading state
        if (loadingOverlay) loadingOverlay.style.display = 'flex';
        outputDiv.innerHTML = '<div class="text-muted">Exécution en cours...</div>';

        try {
            const activityId = window.location.pathname.match(/\/activity\/(\d+)/)?.[1];
            const endpoint = activityId ? `/activity/${activityId}/submit` : '/execute';

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ code, language })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Error executing code');
            }

            if (data.error) {
                outputDiv.innerHTML = `<pre class="error">${data.error}</pre>`;
            } else if (data.test_results) {
                const resultsHtml = data.test_results.map(result => `
                    <div class="test-result ${result.passed ? 'passed' : 'failed'}">
                        <h5 class="mb-2">
                            <i class="bi ${result.passed ? 'bi-check-circle-fill text-success' : 'bi-x-circle-fill text-danger'}"></i>
                            Test Case ${result.passed ? 'Passed' : 'Failed'}
                        </h5>
                        ${result.input ? `<p><strong>Input:</strong> ${result.input}</p>` : ''}
                        <p><strong>Expected:</strong> ${result.expected}</p>
                        <p><strong>Actual:</strong> ${result.actual || 'No output'}</p>
                        ${result.error ? `<p class="text-danger"><strong>Error:</strong> ${result.error}</p>` : ''}
                    </div>
                `).join('');
                outputDiv.innerHTML = resultsHtml;
            } else {
                outputDiv.innerHTML = `<pre>${data.output || 'No output'}</pre>`;
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