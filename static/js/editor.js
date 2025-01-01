
document.addEventListener('DOMContentLoaded', initMonaco);

function initMonaco() {
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs/loader.js';
    script.onload = () => {
        const require = window.require;
        require.config({
            paths: {
                'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs'
            }
        });

        window.MonacoEnvironment = {
            getWorkerUrl: function(workerId, label) {
                return `data:text/javascript;charset=utf-8,${encodeURIComponent(`
                    self.MonacoEnvironment = {
                        baseUrl: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/'
                    };
                    importScripts('https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs/base/worker/workerMain.js');`
                )}`;
            }
        };

        require(['vs/editor/editor.main'], function() {
            const editor = monaco.editor.create(document.getElementById('editor'), {
                value: document.getElementById('initial-code')?.value || '',
                language: 'cpp',
                theme: 'vs-dark',
                automaticLayout: true
            });

            window.codeEditor = editor;

            // Add language switching handler
            const languageSelect = document.getElementById('language');
            if (languageSelect) {
                languageSelect.addEventListener('change', function() {
                    monaco.editor.setModelLanguage(editor.getModel(), this.value);
                });
            }
        });
    };
    document.head.appendChild(script);
}

function executeCode() {
    const code = window.codeEditor.getValue();
    const language = document.getElementById('language').value;

    fetch('/execute', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code, language })
    })
    .then(response => response.json())
    .then(data => {
        const outputDiv = document.getElementById('output');
        if (data.error) {
            outputDiv.innerHTML = `<pre class="error">${data.error}</pre>`;
        } else {
            outputDiv.innerHTML = `<pre>${data.output}</pre>`;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('output').innerHTML = '<pre class="error">Error executing code</pre>';
    });
}
