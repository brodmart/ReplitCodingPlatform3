
document.addEventListener('DOMContentLoaded', function() {
    const editor = CodeMirror.fromTextArea(document.getElementById('editor'), {
        lineNumbers: true,
        theme: 'dracula',
        mode: 'text/x-c++src',
        indentUnit: 4,
        autoCloseBrackets: true,
        matchBrackets: true,
        lineWrapping: true,
        viewportMargin: Infinity
    });

    const languageSelect = document.getElementById('languageSelect');
    languageSelect.addEventListener('change', function() {
        editor.setOption('mode', this.value);
    });

    const runButton = document.getElementById('runButton');
    runButton.addEventListener('click', function() {
        const code = editor.getValue();
        const language = languageSelect.value === 'text/x-c++src' ? 'cpp' : 'csharp';
        const outputDiv = document.getElementById('output');
        
        outputDiv.innerHTML = '<div class="text-muted">Executing code...</div>';

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
            if (data.error) {
                outputDiv.innerHTML = `<pre class="error">${data.error}</pre>`;
            } else {
                outputDiv.innerHTML = `<pre>${data.output}</pre>`;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            outputDiv.innerHTML = '<pre class="error">Error executing code</pre>';
        });
    });
});
