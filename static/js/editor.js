
let editor = null;

// Initialize Monaco editor
function initMonaco() {
    if (editor) return;
    
    const editorContainer = document.getElementById('editor');
    if (!editorContainer) return;

    editor = monaco.editor.create(editorContainer, {
        value: '',
        language: 'cpp',
        theme: 'vs-dark',
        automaticLayout: true,
        minimap: { enabled: false },
        fontSize: 14,
        scrollBeyondLastLine: false,
        renderLineHighlight: 'all',
        tabSize: 2,
        wordWrap: 'on'
    });

    // Language selection handler
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            monaco.editor.setModelLanguage(editor.getModel(), this.value);
        });
    }

    // Run button handler
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', executeCode);
    }

    // Set initial language
    const defaultLanguage = document.getElementById('languageSelect')?.value || 'cpp';
    monaco.editor.setModelLanguage(editor.getModel(), defaultLanguage);
}

// Execute code function
function executeCode() {
    if (!editor) return;
    
    const code = editor.getValue();
    const language = document.getElementById('languageSelect').value;
    const outputDiv = document.getElementById('output');
    
    // Show loading state
    outputDiv.innerHTML = '<div class="text-muted">Executing code...</div>';

    fetch('/execute', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ code, language })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            outputDiv.innerHTML = `<pre class="error">${data.error}</pre>`;
        } else {
            outputDiv.innerHTML = `<pre>${data.output}</pre>`;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        outputDiv.innerHTML = '<pre class="error">Error executing code</pre>';
    });
}

// Load editor when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMonaco);
} else {
    initMonaco();
}
