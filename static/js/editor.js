
// Initialize Monaco Editor
document.addEventListener('DOMContentLoaded', function() {
    initMonaco();
});

async function initMonaco() {
    try {
        // Load Monaco editor from CDN
        const monaco_script = document.createElement('script');
        monaco_script.src = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs/loader.js';
        
        document.body.appendChild(monaco_script);
        
        monaco_script.onload = () => {
            require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs' }});
            require(['vs/editor/editor.main'], function() {
                const editor = monaco.editor.create(document.getElementById('editor'), {
                    value: document.getElementById('initial-code').value || '',
                    language: 'cpp',
                    theme: 'vs-dark',
                    automaticLayout: true
                });
                
                // Make editor instance globally available
                window.codeEditor = editor;
            });
        };
    } catch (error) {
        console.error('Failed to initialize editor:', error);
    }
}

function executeCode() {
    const code = window.codeEditor.getValue();
    const language = document.getElementById('language').value || 'cpp';
    
    fetch('/execute', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            code: code,
            language: language
        })
    })
    .then(response => response.json())
    .then(data => {
        const outputElement = document.getElementById('output');
        if (data.error) {
            outputElement.innerHTML = `<pre class="text-danger">${data.error}</pre>`;
        } else {
            outputElement.innerHTML = `<pre>${data.output}</pre>`;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('output').innerHTML = '<pre class="text-danger">An error occurred while executing the code.</pre>';
    });
}
