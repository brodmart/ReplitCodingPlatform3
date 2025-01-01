
let editor = null;

function initMonaco() {
    if (editor) return;

    require.config({ 
        paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs' }
    });

    require(['vs/editor/editor.main'], function() {
        editor = monaco.editor.create(document.getElementById('editor'), {
            value: '',
            language: 'cpp',
            theme: 'vs-dark',
            automaticLayout: true
        });

        const languageSelect = document.getElementById('languageSelect');
        if (languageSelect) {
            languageSelect.addEventListener('change', function() {
                monaco.editor.setModelLanguage(editor.getModel(), this.value);
            });
        }

        const runButton = document.getElementById('runButton');
        if (runButton) {
            runButton.addEventListener('click', executeCode);
        }
    });
}

function executeCode() {
    if (!editor) return;
    
    const code = editor.getValue();
    const language = document.getElementById('languageSelect').value;

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

window.onload = initMonaco;
