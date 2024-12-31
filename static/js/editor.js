
// Initialize Monaco Editor
let editor;

function initMonaco() {
    require.config({ paths: { 'vs': '/vs' }});
    
    import('/vs/editor/editor.main.js').then(() => {
        editor = monaco.editor.create(document.getElementById('editor'), {
            value: '',
            language: 'cpp',
            theme: 'vs-dark',
            automaticLayout: true
        });
    }).catch(err => {
        console.error('Failed to initialize editor:', err);
    });
}

function executeCode() {
    if (!editor) return;
    
    const code = editor.getValue();
    const language = document.getElementById('language').value;

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
            outputElement.innerText = data.error;
            outputElement.classList.add('error');
        } else {
            outputElement.innerText = data.output;
            outputElement.classList.remove('error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

document.addEventListener('DOMContentLoaded', initMonaco);
