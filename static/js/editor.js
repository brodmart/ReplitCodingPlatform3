
let editor = null;
let isEditorInitialized = false;

function initializeEditor() {
    if (isEditorInitialized) return;
    
    const editorElement = document.getElementById('editor');
    if (!editorElement) return;

    try {
        require(['vs/editor/editor.main'], function() {
            editor = monaco.editor.create(editorElement, {
                value: '// Your code here',
                language: 'cpp',
                theme: 'vs-dark',
                minimap: { enabled: false },
                automaticLayout: true,
                fontSize: 14
            });

            const languageSelect = document.getElementById('languageSelect');
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

            isEditorInitialized = true;
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
    const languageSelect = document.getElementById('languageSelect');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

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

// Initialize editor when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeEditor);
