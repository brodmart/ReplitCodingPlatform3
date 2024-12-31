
import * as monaco from 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/editor/editor.main.js';

let editor;

document.addEventListener('DOMContentLoaded', async function initMonaco() {
    editor = await monaco.editor.create(document.getElementById('editor'), {
        value: '',
        language: 'cpp',
        theme: 'vs-dark',
        automaticLayout: true
    });
});

function executeCode() {
    if (!editor) return;
    const code = editor.getValue();
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
        const output = document.getElementById('output');
        if (data.error) {
            output.innerHTML = `<pre class="error">${data.error}</pre>`;
        } else {
            output.innerHTML = `<pre class="success">${data.output}</pre>`;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('output').innerHTML = '<pre class="error">Une erreur est survenue lors de l\'exécution</pre>';
    });
}

window.executeCode = executeCode;
