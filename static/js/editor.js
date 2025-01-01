
document.addEventListener('DOMContentLoaded', function() {
    // Initialize CodeMirror editor
    const editor = CodeMirror.fromTextArea(document.getElementById('editor'), {
        lineNumbers: true,
        mode: 'text/x-c++src',
        theme: 'default',
        autoCloseBrackets: true,
        matchBrackets: true,
        indentUnit: 4,
        tabSize: 4
    });

    // Language switching
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const mode = this.value === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
            editor.setOption('mode', mode);
        });
    }

    // Run button functionality
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', function() {
            const code = editor.getValue();
            const language = languageSelect ? languageSelect.value : 'cpp';
            
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
        });
    }
});
