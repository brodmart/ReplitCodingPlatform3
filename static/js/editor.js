
// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }});

    // Load Monaco
    require(['vs/editor/editor.main'], function() {
        initializeEditor();
    });
});

let editor = null;
let languageSelect = null;

function initializeEditor() {
    try {
        const editorElement = document.getElementById('editor');
        languageSelect = document.getElementById('languageSelect');
        
        if (!editorElement) {
            console.error('Editor element not found');
            return;
        }

        editor = monaco.editor.create(editorElement, {
            value: '// Your code here',
            language: languageSelect ? languageSelect.value : 'cpp',
            theme: 'vs-dark',
            minimap: { enabled: false },
            automaticLayout: true,
            fontSize: 14,
            scrollBeyondLastLine: false
        });

        // Set up event listeners
        if (languageSelect) {
            languageSelect.addEventListener('change', function() {
                if (editor && editor.getModel()) {
                    monaco.editor.setModelLanguage(editor.getModel(), this.value);
                }
            });
        }

        const runButton = document.getElementById('runButton');
        if (runButton) {
            runButton.addEventListener('click', executeCode);
        }

        // Handle window resize
        window.addEventListener('resize', function() {
            if (editor) {
                editor.layout();
            }
        });

    } catch (error) {
        console.error('Editor initialization failed:', error);
    }
}

async function executeCode() {
    if (!editor) {
        console.error('Editor not initialized');
        return;
    }

    const output = document.getElementById('output');
    if (!output) {
        console.error('Output element not found');
        return;
    }

    try {
        const code = editor.getValue();
        const language = languageSelect ? languageSelect.value : 'cpp';
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

        if (!csrfToken) {
            throw new Error('CSRF token not found');
        }

        const response = await fetch('/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ code, language })
        });

        const result = await response.json();
        
        if (result.error) {
            output.innerHTML = `<pre class="error">${result.error}</pre>`;
        } else {
            output.innerHTML = `<pre>${result.output}</pre>`;
        }
    } catch (error) {
        console.error('Code execution failed:', error);
        output.innerHTML = `<pre class="error">Error: ${error.message}</pre>`;
    }
}
