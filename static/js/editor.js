// Wait for DOM and scripts to load
document.addEventListener('DOMContentLoaded', function() {
    try {
        // Make sure CodeMirror is loaded
        if (typeof CodeMirror === 'undefined') {
            throw new Error('CodeMirror library not loaded');
        }

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
                },
                "Ctrl-F": "find",
                "Cmd-F": "find"
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
            runButton.addEventListener('click', async function() {
                const loadingOverlay = document.getElementById('loadingOverlay');
                const outputDiv = document.getElementById('output');
                const code = editor.getValue();
                const language = languageSelect ? languageSelect.value : 'cpp';

                try {
                    // Show loading state
                    loadingOverlay.classList.add('show');
                    outputDiv.innerHTML = '<div class="text-muted">Exécution en cours...</div>';
                    setTimeout(() => {
                        if (outputDiv.innerHTML.includes('Exécution en cours')) {
                            outputDiv.innerHTML = '<div class="error">L\'exécution a pris trop de temps. Veuillez réessayer.</div>';
                        }
                    }, 15000);

                    // Get the activity ID from the URL if we're on an activity page
                    const activityId = window.location.pathname.match(/\/activity\/(\d+)/)?.[1];
                    const endpoint = activityId ? `/activities/activity/${activityId}/submit` : '/execute';

                    const response = await fetch(endpoint, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ code, language })
                    });

                    const data = await response.json();

                    if (!response.ok) {
                        throw new Error(data.error || 'Error executing code');
                    }

                    if (data.error) {
                        outputDiv.innerHTML = `<pre class="error">${data.error}</pre>`;
                    } else if (data.test_results) {
                        // Handle activity submission results
                        const resultsHtml = data.test_results.map(result => `
                            <div class="test-result ${result.passed ? 'passed' : 'failed'}">
                                <h5 class="mb-2">
                                    <i class="bi ${result.passed ? 'bi-check-circle-fill text-success' : 'bi-x-circle-fill text-danger'}"></i>
                                    Test Case ${result.passed ? 'Passed' : 'Failed'}
                                </h5>
                                ${result.input ? `<p><strong>Input:</strong> ${result.input}</p>` : ''}
                                <p><strong>Expected:</strong> ${result.expected}</p>
                                <p><strong>Actual:</strong> ${result.actual || 'No output'}</p>
                                ${result.error ? `<p class="text-danger"><strong>Error:</strong> ${result.error}</p>` : ''}
                            </div>
                        `).join('');
                        outputDiv.innerHTML = resultsHtml;
                    } else {
                        outputDiv.innerHTML = `<pre>${data.output || 'No output'}</pre>`;
                    }
                } catch (error) {
                    console.error('Error:', error);
                    outputDiv.innerHTML = `<pre class="error">${error.message || 'Error executing code'}</pre>`;
                } finally {
                    // Always hide loading overlay
                    loadingOverlay.classList.remove('show');
                }
            });
        }

        // Trigger initial setup
        editor.refresh();

        console.log('CodeMirror editor initialized successfully');
    } catch (error) {
        console.error('Failed to initialize editor:', error);
        document.getElementById('editor').style.display = 'none';
        document.getElementById('output').innerHTML = `
            <div class="alert alert-danger">
                Failed to initialize code editor. Please refresh the page or contact support if the issue persists.
            </div>
        `;
    }
});