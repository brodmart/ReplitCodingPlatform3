
let editor = null;

// Wait for Monaco to be loaded
window.addEventListener('load', function() {
    require.config({
        paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }
    });

    require(['vs/editor/editor.main'], function() {
        const editorElement = document.getElementById('editor');
        if (!editorElement) return;

        try {
            editor = monaco.editor.create(editorElement, {
                value: '// Your code here',
                language: 'cpp',
                theme: 'vs-dark',
                minimap: { enabled: false },
                automaticLayout: true,
                fontSize: 14
            });

            // Set up language change handler
            const languageSelect = document.getElementById('languageSelect');
            if (languageSelect) {
                languageSelect.addEventListener('change', function() {
                    if (editor && editor.getModel()) {
                        monaco.editor.setModelLanguage(editor.getModel(), this.value);
                    }
                });
            }

            // Set up run button handler
            const runButton = document.getElementById('runButton');
            if (runButton) {
                runButton.addEventListener('click', executeCode);
            }
        } catch (error) {
            console.error('Editor initialization failed:', error);
        }
    });
});

async function executeCode() {
    if (!editor) {
        console.error('Editor not initialized');
        return;
    }

    const output = document.getElementById('output');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const languageSelect = document.getElementById('languageSelect');
    
    if (!csrfToken) {
        console.error('CSRF token not available');
        return;
    }

    try {
        const code = editor.getValue();
        const language = languageSelect ? languageSelect.value : 'cpp';

        const response = await fetch('/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ code, language })
        });

        const result = await response.json();
        if (output) {
            output.innerHTML = `<pre class="${result.success ? 'success' : 'error'}">${result.output || result.error}</pre>`;
        }
    } catch (error) {
        if (output) {
            output.innerHTML = `<pre class="error">Error: ${error.message}</pre>`;
        }
        console.error('Code execution failed:', error);
    }
}
