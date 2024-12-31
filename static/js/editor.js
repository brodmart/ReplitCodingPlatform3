
// Global editor instance
let editor = null;

// Initialize editor
function initEditor() {
    if (editor) return;  // Prevent multiple initializations
    
    const editorElement = document.getElementById('editor');
    if (!editorElement) return;

    // Initialize Monaco
    monaco.editor.create(editorElement, {
        value: '// Your code here',
        language: 'cpp',
        theme: 'vs-dark',
        minimap: { enabled: false },
        automaticLayout: true,
        scrollBeyondLastLine: false
    });

    // Handle language selection
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            monaco.editor.setModelLanguage(editor.getModel(), this.value);
        });
    }

    // Handle run button
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', async function() {
            const output = document.getElementById('output');
            if (!output) return;

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

// Load Monaco
if (document.getElementById('editor')) {
    require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }});
    require(['vs/editor/editor.main'], initEditor);
}
