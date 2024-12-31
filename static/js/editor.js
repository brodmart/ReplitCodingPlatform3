
// Global editor instance
let editor = null;
let initialized = false;

// Configure Monaco loader
require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }});

// Initialize editor once
function initEditor() {
    if (initialized) return;
    
    const editorElement = document.getElementById('editor');
    if (!editorElement) return;

    require(['vs/editor/editor.main'], function() {
        if (editor) {
            editor.dispose();
        }

        editor = monaco.editor.create(editorElement, {
            value: '// Your code here',
            language: 'cpp',
            theme: 'vs-dark',
            minimap: { enabled: false },
            automaticLayout: true,
            scrollBeyondLastLine: false,
            fontSize: 14
        });

        const languageSelect = document.getElementById('languageSelect');
        if (languageSelect) {
            languageSelect.addEventListener('change', () => {
                if (editor) {
                    monaco.editor.setModelLanguage(editor.getModel(), languageSelect.value);
                }
            });
        }

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

        initialized = true;
    });
}

// Initialize editor when DOM is loaded
document.addEventListener('DOMContentLoaded', initEditor);

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (editor) {
        editor.dispose();
        editor = null;
        initialized = false;
    }
});
