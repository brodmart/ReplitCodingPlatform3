document.addEventListener('DOMContentLoaded', function() {
    // Initialize CodeMirror with enhanced features
    const editor = CodeMirror.fromTextArea(document.getElementById('editor'), {
        mode: 'text/x-c++src',
        theme: 'dracula',
        lineNumbers: true,
        matchBrackets: true,
        autoCloseBrackets: true,
        indentUnit: 4,
        tabSize: 4,
        viewportMargin: Infinity,
        lineWrapping: true,
        foldGutter: true,
        gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
        extraKeys: {
            "Ctrl-Space": "autocomplete",
            "F11": function(cm) {
                cm.setOption("fullScreen", !cm.getOption("fullScreen"));
            },
            "Esc": function(cm) {
                if (cm.getOption("fullScreen")) cm.setOption("fullScreen", false);
            }
        },
        styleActiveLine: true,
        autoCloseTags: true,
        highlightSelectionMatches: {showToken: /\w/, annotateScrollbar: true}
    });

    // Language switching
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const mode = this.value === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
            editor.setOption('mode', mode);
        });
    }

    // Code execution
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', function() {
            const code = editor.getValue();
            const language = languageSelect ? languageSelect.value : 'cpp';
            const outputDiv = document.getElementById('output');

            outputDiv.innerHTML = '<div class="text-muted">Executing code...</div>';

            fetch('/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
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
    }

    // Trigger initial setup
    editor.refresh();
});