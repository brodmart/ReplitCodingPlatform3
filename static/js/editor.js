
document.addEventListener('DOMContentLoaded', function() {
    const editorElement = document.getElementById('editor');
    if (!editorElement) return;

    const language = editorElement.dataset.language || 'cpp';
    const initialValue = editorElement.dataset.initialValue || '';

    require.config({ paths: { 'vs': 'https://unpkg.com/monaco-editor@latest/min/vs' }});
    window.MonacoEnvironment = { getWorkerUrl: () => proxy };

    let proxy = URL.createObjectURL(new Blob([`
        self.MonacoEnvironment = {
            baseUrl: 'https://unpkg.com/monaco-editor@latest/min/'
        };
        importScripts('https://unpkg.com/monaco-editor@latest/min/vs/base/worker/workerMain.js');
    `], { type: 'text/javascript' }));

    require(['vs/editor/editor.main'], function() {
        window.editor = monaco.editor.create(editorElement, {
            value: initialValue,
            language: language,
            theme: 'vs-dark',
            minimap: { enabled: false },
            automaticLayout: true
        });
    });
});

function executeCode() {
    const loadingOverlay = document.getElementById('loadingOverlay');
    const outputDiv = document.getElementById('output');
    const code = window.editor.getValue();

    loadingOverlay.style.display = 'flex';
    outputDiv.innerHTML = '';

    fetch(window.location.pathname + '/submit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code: code })
    })
    .then(response => response.json())
    .then(data => {
        loadingOverlay.style.display = 'none';
        let output = '<div class="test-results">';
        
        if (data.test_results) {
            data.test_results.forEach((result, index) => {
                output += `<div class="test-case ${result.passed ? 'passed' : 'failed'}">`;
                output += `<h6>Test Case ${index + 1}</h6>`;
                if (result.input) output += `<p>Input: ${result.input}</p>`;
                output += `<p>Expected: ${result.expected}</p>`;
                output += `<p>Actual: ${result.actual || 'No output'}</p>`;
                if (result.error) output += `<p class="error">Error: ${result.error}</p>`;
                output += '</div>';
            });
        }
        
        output += '</div>';
        outputDiv.innerHTML = output;
    })
    .catch(error => {
        loadingOverlay.style.display = 'none';
        outputDiv.innerHTML = `<div class="error">Error: ${error.message}</div>`;
    });
}
