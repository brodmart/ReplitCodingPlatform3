
// Global editor instance
let editor = null;
let monacoLoaded = false;

// Configure Monaco loader once
require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }});

// Initialize editor only once
async function initMonaco(elementId = 'editor') {
    const editorElement = document.getElementById(elementId);
    if (!editorElement || editor) return;

    if (!monacoLoaded) {
        await new Promise((resolve) => {
            require(['vs/editor/editor.main'], resolve);
            monacoLoaded = true;
        });
    }

    editor = monaco.editor.create(editorElement, {
        value: editorElement.dataset.initialValue || '// Your code here',
        language: editorElement.dataset.language || 'cpp',
        theme: 'vs-dark',
        minimap: { enabled: false },
        automaticLayout: true,
        scrollBeyondLastLine: false,
        fontSize: 14
    });

    // Setup language selector if present
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', () => {
            monaco.editor.setModelLanguage(editor.getModel(), languageSelect.value);
        });
    }

    // Setup run button if present
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', async () => {
            const output = document.getElementById('output');
            if (!output || !editor) return;

            try {
                const response = await fetch('/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
                    },
                    body: JSON.stringify({
                        code: editor.getValue(),
                        language: languageSelect ? languageSelect.value : 'cpp'
                    })
                });

                const result = await response.json();
                output.innerHTML = `<pre>${result.error ? `<span class="error">${result.error}</span>` : result.output}</pre>`;
            } catch (error) {
                output.innerHTML = `<pre class="error">Error: ${error.message}</pre>`;
            }
        });
    }
}

// Initialize when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initMonaco());
} else {
    initMonaco();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (editor) {
        editor.dispose();
        editor = null;
    }
});
