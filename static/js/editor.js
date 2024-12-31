
// Single editor instance
let editor = null;

// Configure Monaco loader
require.config({
    paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }
});

// Initialize editor only once
function initEditor() {
    if (editor) return;
    
    const editorElement = document.getElementById('editor');
    if (!editorElement) return;

    const initialValue = editorElement.dataset.initialValue || '// Your code here';
    const language = editorElement.dataset.language || 'cpp';

    editor = monaco.editor.create(editorElement, {
        value: initialValue,
        language: language,
        theme: 'vs-dark',
        minimap: { enabled: false },
        automaticLayout: true,
        fontSize: 14
    });

    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            monaco.editor.setModelLanguage(editor.getModel(), this.value);
        });
    }
}

// Execute code function
async function executeCode() {
    if (!editor) return;

    const output = document.getElementById('output');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const languageSelect = document.getElementById('languageSelect');
    
    if (!csrfToken) {
        console.error('CSRF token not available');
        return;
    }

    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) loadingOverlay.style.display = 'flex';

    try {
        const response = await fetch('/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                code: editor.getValue(),
                language: languageSelect ? languageSelect.value : 'cpp'
            })
        });

        const result = await response.json();
        if (output) {
            output.innerHTML = `<pre class="${result.success ? 'success' : 'error'}">${result.output || result.error}</pre>`;
        }
    } catch (error) {
        if (output) {
            output.innerHTML = `<pre class="error">Error: ${error.message}</pre>`;
        }
    } finally {
        if (loadingOverlay) loadingOverlay.style.display = 'none';
    }
}

// Wait for Monaco to load then initialize
require(['vs/editor/editor.main'], function() {
    initEditor();
    
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', executeCode);
    }
});
