
// Initialize editor only once
let editor = null;
let isEditorInitialized = false;

// Wait for document to load
document.addEventListener('DOMContentLoaded', function() {
    if (isEditorInitialized) return;
    
    const editorElement = document.getElementById('editor');
    if (!editorElement) return;

    require(['vs/editor/editor.main'], function() {
        try {
            if (editor) {
                editor.dispose();
            }

            editor = monaco.editor.create(editorElement, {
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
                    if (editor) {
                        monaco.editor.setModelLanguage(editor.getModel(), this.value);
                    }
                });
            }

            // Handle run button
            const runButton = document.getElementById('runButton');
            if (runButton) {
                runButton.addEventListener('click', async function() {
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

            isEditorInitialized = true;
        } catch (error) {
            console.error('Failed to initialize editor:', error);
        }
    });
});

// Cleanup on page unload
window.addEventListener('unload', function() {
    if (editor) {
        editor.dispose();
        editor = null;
        isEditorInitialized = false;
    }
});
