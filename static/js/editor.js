
document.addEventListener('DOMContentLoaded', function() {
    const runButton = document.getElementById('runButton');
    
    if (runButton) {
        runButton.addEventListener('click', executeCode);
    }
});

function executeCode() {
    const code = document.getElementById('editor').value;
    const language = document.getElementById('languageSelect').value;
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
}
