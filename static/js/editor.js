
// Initialize Monaco Editor
document.addEventListener('DOMContentLoaded', function() {
    const editorElement = document.getElementById('editor');
    if (!editorElement) return;

    const language = editorElement.dataset.language || 'cpp';
    const initialValue = editorElement.dataset.initialValue || '';

    // Create script element for loader
    const loaderScript = document.createElement('script');
    loaderScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs/loader.min.js';
    loaderScript.onload = function() {
        require.config({
            paths: {
                'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs'
            }
        });

        window.MonacoEnvironment = {
            getWorkerUrl: function(workerId, label) {
                return `data:text/javascript;charset=utf-8,${encodeURIComponent(`
                    self.MonacoEnvironment = {
                        baseUrl: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/'
                    };
                    importScripts('https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs/base/worker/workerMain.js');`
                )}`;
            }
        };

        require(['vs/editor/editor.main'], function() {
            window.editor = monaco.editor.create(editorElement, {
                value: initialValue || '',
                language: language,
                theme: 'vs-dark',
                minimap: { enabled: false },
                automaticLayout: true,
                fontSize: 14
            });
        });
    };
    document.body.appendChild(loaderScript);
});

function executeCode() {
    const loadingOverlay = document.getElementById('loadingOverlay');
    const outputDiv = document.getElementById('output');
    
    if (!window.editor) {
        console.error('Editor not initialized');
        return;
    }

    const code = window.editor.getValue();
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

    loadingOverlay.style.display = 'flex';
    outputDiv.innerHTML = '';

    fetch(window.location.pathname + '/submit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
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
