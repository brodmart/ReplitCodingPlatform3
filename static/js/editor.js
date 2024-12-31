
// Single editor instance
let editor = null;
let initialized = false;

// Initialize Monaco only once
function initMonaco() {
    if (initialized || !document.getElementById('editor')) return;
    
    require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }});
    
    window.MonacoEnvironment = { 
        getWorkerUrl: () => {
            return `data:text/javascript;charset=utf-8,${encodeURIComponent(`
                self.MonacoEnvironment = {
                    baseUrl: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/'
                };
                importScripts('https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs/base/worker/workerMain.js');`
            )}`;
        }
    };

    require(['vs/editor/editor.main'], () => {
        if (!document.getElementById('editor')) return;
        
        editor = monaco.editor.create(document.getElementById('editor'), {
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
                monaco.editor.setModelLanguage(editor.getModel(), languageSelect.value);
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

// Initialize once when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMonaco);
} else {
    initMonaco();
}

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (editor) {
        editor.dispose();
        editor = null;
        initialized = false;
    }
});
