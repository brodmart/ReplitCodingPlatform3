// Initialize CodeMirror editor with enhanced settings
document.addEventListener('DOMContentLoaded', function() {
    const editorElement = document.getElementById('editor');
    if (!editorElement) {
        console.error('Editor element not found');
        return;
    }

    // Get initial code from the textarea
    const initialCode = editorElement.value;

    // Initialize CodeMirror with enhanced settings
    const editor = CodeMirror.fromTextArea(editorElement, {
        mode: 'text/x-c++src',
        theme: 'dracula',
        lineNumbers: true,
        autoCloseBrackets: true,
        matchBrackets: true,
        indentUnit: 4,
        tabSize: 4,
        lineWrapping: true,
        gutters: ["CodeMirror-linenumbers", "CodeMirror-lint-markers"],
        lint: true,
        extraKeys: {
            "Ctrl-Space": "autocomplete",
            "F11": function(cm) {
                cm.setOption("fullScreen", !cm.getOption("fullScreen"));
            },
            "Esc": function(cm) {
                if (cm.getOption("fullScreen")) cm.setOption("fullScreen", false);
            }
        }
    });

    // Set initial code and refresh editor
    editor.setValue(initialCode || getTemplateForLanguage('cpp'));
    editor.refresh();

    // Track if code has been executed and modified
    let hasExecuted = false;
    let isModified = false;

    // Store initial template for comparison
    let currentTemplate = getTemplateForLanguage('cpp');

    // Error marker management
    let errorMarkers = [];

    function clearErrorMarkers() {
        errorMarkers.forEach(marker => marker.clear());
        errorMarkers = [];
    }

    function addErrorMarker(line, message) {
        const lineNumber = line - 1;  // CodeMirror lines are 0-based
        const marker = editor.markText(
            {line: lineNumber, ch: 0},
            {line: lineNumber, ch: editor.getLine(lineNumber).length},
            {
                className: 'error-line',
                title: message
            }
        );
        errorMarkers.push(marker);
    }

    // Handle language changes
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        const initialLanguage = languageSelect.value || 'cpp';
        editor.setOption('mode', getEditorMode(initialLanguage));

        languageSelect.addEventListener('change', function() {
            const language = this.value;
            const currentCode = editor.getValue().trim();

            // Clear any existing error markers
            clearErrorMarkers();

            // Always update the editor mode for proper syntax highlighting
            editor.setOption('mode', getEditorMode(language));

            // Reset to template if:
            // 1. Code has been executed
            // 2. Current code matches other language's characteristics
            // 3. Editor is empty
            if (hasExecuted || shouldUseTemplate(currentCode, language) || !currentCode) {
                const newTemplate = getTemplateForLanguage(language);
                editor.setValue(newTemplate);
                currentTemplate = newTemplate;
                isModified = false;
                hasExecuted = false;
            }

            editor.refresh();
        });
    }

    // Handle code changes
    editor.on('change', function() {
        const currentCode = editor.getValue().trim();
        isModified = currentCode !== currentTemplate.trim();
        clearErrorMarkers();  // Clear error markers when code changes
    });

    // Helper function to get editor mode based on language
    function getEditorMode(language) {
        return language === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
    }

    // Helper function to determine if we should use template
    function shouldUseTemplate(currentCode, newLanguage) {
        if (!currentCode) return true;

        // Check if the current code matches either language's characteristics
        const isCppCode = currentCode.includes('#include') || 
                         currentCode.includes('using namespace std') ||
                         currentCode.includes('int main()');

        const isCsharpCode = currentCode.includes('using System') || 
                            currentCode.includes('class Program') ||
                            currentCode.includes('static void Main');

        // If switching from C++ to C# or vice versa, use template
        return (newLanguage === 'cpp' && isCsharpCode) || 
               (newLanguage === 'csharp' && isCppCode);
    }

    // Helper function to get template for specific language
    function getTemplateForLanguage(language) {
        if (language === 'cpp') {
            return `#include <iostream>
using namespace std;

int main() {
    // Votre code ici
    return 0;
}`;
        } else {
            return `using System;

class Program {
    static void Main() {
        // Votre code ici
    }
}`;
        }
    }

    // Enhanced error display in output
    function displayError(outputDiv, error) {
        if (typeof error === 'object' && error.error_details) {
            // Clear previous error markers
            clearErrorMarkers();

            // Add new error marker
            addErrorMarker(error.error_details.line, error.error_details.message);

            // Display formatted error message
            outputDiv.innerHTML = `
                <div class="alert alert-danger">
                    <strong>Erreur ligne ${error.error_details.line}:</strong>
                    <pre>${error.error_details.message}</pre>
                </div>`;
        } else {
            outputDiv.innerHTML = `
                <div class="alert alert-danger">
                    <pre>${error}</pre>
                </div>`;
        }
    }

    // Handle run button clicks with enhanced error handling
    const runButton = document.getElementById('runButton');
    const outputDiv = document.getElementById('output');
    if (runButton && outputDiv) {
        runButton.addEventListener('click', async function() {
            const code = editor.getValue().trim();
            if (!code) {
                outputDiv.innerHTML = '<div class="alert alert-warning">Le code ne peut pas être vide</div>';
                return;
            }

            // Update UI for execution
            runButton.disabled = true;
            outputDiv.innerHTML = '<div class="loading">Exécution du code...</div>';
            clearErrorMarkers();
            hasExecuted = true;

            try {
                // Get CSRF token from meta tag
                const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
                if (!csrfToken) {
                    throw new Error('CSRF token not found');
                }

                const response = await fetch('/activities/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify({
                        code,
                        language: languageSelect ? languageSelect.value : 'cpp'
                    })
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => null);
                    throw new Error(errorData?.error || `HTTP error! status: ${response.status}`);
                }

                const data = await response.json();

                if (!data.success) {
                    displayError(outputDiv, data.error);
                } else {
                    clearErrorMarkers();
                    outputDiv.innerHTML = `
                        <pre class="p-3 bg-dark text-light rounded">${data.output || 'Pas de sortie'}</pre>
                        ${data.error ? `<div class="alert alert-warning mt-2">${data.error}</div>` : ''}
                    `;
                }
            } catch (error) {
                console.error('Execution error:', error);
                outputDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <strong>Erreur d'exécution:</strong>
                        <pre>${error.message}</pre>
                    </div>`;
            } finally {
                runButton.disabled = false;
            }
        });
    }

    // Add custom styles for error highlighting
    const style = document.createElement('style');
    style.textContent = `
        .error-line {
            background-color: rgba(255, 0, 0, 0.2);
            border-bottom: 2px solid #ff0000;
        }
        .loading {
            padding: 1rem;
            text-align: center;
            color: #666;
        }
        .alert {
            margin-bottom: 0;
        }
        .alert pre {
            margin-bottom: 0;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
    `;
    document.head.appendChild(style);

    // Log successful initialization
    console.log('Editor initialized successfully');
});