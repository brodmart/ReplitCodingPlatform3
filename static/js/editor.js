// Initialize CodeMirror editor with enhanced settings
document.addEventListener('DOMContentLoaded', function() {
    const editorElement = document.getElementById('editor');
    if (!editorElement) {
        console.error('Editor element not found');
        return;
    }

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

    // Set initial code with template
    const initialLanguage = languageSelect ? languageSelect.value : 'cpp';
    const initialTemplate = getTemplateForLanguage(initialLanguage);
    editor.setValue(initialTemplate);
    editor.refresh();

    // Get CSRF token from meta tag
    const getCsrfToken = () => {
        const tokenMeta = document.querySelector('meta[name="csrf-token"]');
        if (!tokenMeta) {
            console.error('CSRF token meta tag not found');
            return null;
        }
        return tokenMeta.content;
    };

    // Track if code has been executed and modified
    let hasExecuted = false;
    let isModified = false;

    // Store initial template for comparison
    let currentTemplate = getTemplateForLanguage('cpp');

    // Error marker management
    let errorMarkers = [];
    let errorWidgets = [];

    function clearErrorIndicators() {
        // Clear error markers
        errorMarkers.forEach(marker => marker.clear());
        errorMarkers = [];

        // Clear error widgets
        errorWidgets.forEach(widget => widget.clear());
        errorWidgets = [];

        // Clear error line classes
        editor.eachLine(line => {
            editor.removeLineClass(line, 'background', 'error-line');
            editor.removeLineClass(line, 'background', 'warning-line');
        });
    }

    function addErrorHighlight(line, type = 'error') {
        const lineNumber = line - 1;  // CodeMirror lines are 0-based
        const lineHandle = editor.getLineHandle(lineNumber);
        if (lineHandle) {
            editor.addLineClass(lineHandle, 'background', `${type}-line`);
        }
    }

    function addErrorWidget(line, message, type = 'error') {
        const lineNumber = line - 1;
        const widget = document.createElement('div');
        widget.className = `compiler-${type}-widget`;
        widget.innerHTML = `<i class="bi ${type === 'error' ? 'bi-exclamation-circle' : 'bi-exclamation-triangle'}"></i> ${message}`;

        const widgetMarker = editor.addLineWidget(lineNumber, widget, {
            coverGutter: false,
            noHScroll: true
        });
        errorWidgets.push(widgetMarker);
    }

    // Handle language changes
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        const initialLanguage = languageSelect.value || 'cpp';
        editor.setOption('mode', getEditorMode(initialLanguage));

        languageSelect.addEventListener('change', function() {
            const language = this.value;
            console.log("Switching to language:", language);

            // Clear any existing error indicators
            clearErrorIndicators();

            // Update editor mode for proper syntax highlighting
            const mode = getEditorMode(language);
            console.log("Setting mode to:", mode);
            editor.setOption('mode', mode);

            // Reset to template if needed
            if (hasExecuted || shouldUseTemplate(editor.getValue().trim(), language) || !editor.getValue().trim()) {
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
        clearErrorIndicators();  // Clear error indicators when code changes
    });

    // Helper function to get editor mode based on language
    function getEditorMode(language) {
        return language === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
    }

    // Helper function to determine if we should use template
    function shouldUseTemplate(currentCode, newLanguage) {
        if (!currentCode) return true;

        const isCppCode = currentCode.includes('#include') || 
                         currentCode.includes('using namespace std') ||
                         currentCode.includes('int main()');

        const isCsharpCode = currentCode.includes('using System') || 
                            currentCode.includes('class Program') ||
                            currentCode.includes('static void Main');

        return (newLanguage === 'cpp' && isCsharpCode) || 
               (newLanguage === 'csharp' && isCppCode);
    }

    // Helper function to get template for specific language
    function getTemplateForLanguage(language) {
        if (language === 'cpp') {
            return `#include <iostream>
#include <string>
using namespace std;

int main() {
    // Votre code ici
    return 0;
}`;
        } else {
            return `using System;

namespace ProgrammingActivity
{
    class Program 
    {
        static void Main(string[] args)
        {
            // Votre code ici
        }
    }
}`;
        }
    }

    // Enhanced error display in output with visual indicators
    function displayError(outputDiv, error) {
        clearErrorIndicators();

        if (typeof error === 'object' && error.error_details) {
            const { line, message, type = 'error' } = error.error_details;

            // Add visual indicators
            addErrorHighlight(line, type);
            addErrorWidget(line, message, type);

            // Update output div with formatted message
            outputDiv.innerHTML = `
                <div class="alert alert-${type === 'error' ? 'danger' : 'warning'}">
                    <div class="d-flex align-items-center mb-2">
                        <i class="bi ${type === 'error' ? 'bi-exclamation-circle' : 'bi-exclamation-triangle'} me-2"></i>
                        <strong>${type === 'error' ? 'Erreur' : 'Avertissement'} ligne ${line}:</strong>
                    </div>
                    <pre class="mb-0 ps-4">${message}</pre>
                </div>`;
        } else {
            outputDiv.innerHTML = `
                <div class="alert alert-danger">
                    <div class="d-flex align-items-center">
                        <i class="bi bi-exclamation-circle me-2"></i>
                        <pre class="mb-0">${error}</pre>
                    </div>
                </div>`;
        }
    }

    // Handle run button clicks with enhanced error handling and network timeout
    const runButton = document.getElementById('runButton');
    const outputDiv = document.getElementById('output');
    if (runButton && outputDiv) {
        runButton.addEventListener('click', async function() {
            const code = editor.getValue().trim();
            if (!code) {
                outputDiv.innerHTML = '<div class="alert alert-warning">Le code ne peut pas être vide</div>';
                return;
            }

            // Get CSRF token
            const csrfToken = getCsrfToken();
            if (!csrfToken) {
                outputDiv.innerHTML = '<div class="alert alert-danger">Token de sécurité manquant. Veuillez rafraîchir la page.</div>';
                return;
            }

            // Update UI for execution
            runButton.disabled = true;
            let abortController = null;
            try {
                const language = document.getElementById('languageSelect')?.value || 'cpp';
                console.log('Executing code:', { language, codeLength: code.length });

                // Set up timeout for the fetch request
                abortController = new AbortController();
                const timeoutId = setTimeout(() => {
                    abortController.abort();
                    throw new Error('La requête a pris trop de temps. Vérifiez votre connexion et réessayez.');
                }, 10000); // 10 second timeout

                const response = await fetch('/activities/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify({
                        code: code,
                        language: language
                    }),
                    signal: abortController.signal
                });

                clearTimeout(timeoutId);

                if (!response.ok) {
                    if (response.status === 429) {
                        throw new Error('Trop de requêtes. Veuillez attendre quelques secondes avant de réessayer.');
                    }
                    throw new Error(`Erreur serveur (${response.status}). Veuillez réessayer.`);
                }

                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    throw new Error('Le serveur a retourné une réponse invalide. Veuillez rafraîchir la page.');
                }

                const data = await response.json();
                console.log('Execution response:', data);

                if (!data.success) {
                    throw new Error(data.error || 'Une erreur inconnue s\'est produite');
                }

                // Display successful execution
                outputDiv.innerHTML = `
                    <div class="alert alert-success mb-3">
                        <i class="bi bi-check-circle me-2"></i>
                        Code exécuté avec succès
                    </div>
                    <pre class="p-3 bg-dark text-light rounded">${data.output || 'Pas de sortie'}</pre>
                    ${data.error ? `
                        <div class="alert alert-warning mt-3">
                            <i class="bi bi-exclamation-triangle me-2"></i>
                            ${data.error}
                        </div>` : ''}`;

            } catch (error) {
                console.error('Execution error:', error);
                let errorMessage = error.message;

                if (error.name === 'AbortError') {
                    errorMessage = 'La requête a pris trop de temps. Vérifiez votre connexion et réessayez.';
                } else if (!navigator.onLine) {
                    errorMessage = 'Pas de connexion Internet. Vérifiez votre connexion et réessayez.';
                }

                outputDiv.innerHTML = `
                    <div class="alert alert-danger">
                        <div class="d-flex align-items-center mb-2">
                            <i class="bi bi-exclamation-circle me-2"></i>
                            <strong>Erreur:</strong>
                        </div>
                        <pre class="mb-0 ps-4">${errorMessage}</pre>
                    </div>`;
            } finally {
                runButton.disabled = false;
                if (abortController) {
                    try {
                        abortController.abort(); // Clean up any pending request
                    } catch (e) {
                        console.error('Error aborting request:', e);
                    }
                }
            }
        });
    }

    // Add custom styles for error highlighting and widgets
    const style = document.createElement('style');
    style.textContent = `
        .error-line {
            background-color: rgba(255, 0, 0, 0.1);
            border-left: 3px solid #dc3545;
        }
        .warning-line {
            background-color: rgba(255, 193, 7, 0.1);
            border-left: 3px solid #ffc107;
        }
        .compiler-error-widget {
            padding: 0.25rem 0.5rem;
            margin: 0.25rem 0;
            background-color: rgba(220, 53, 69, 0.1);
            border-left: 3px solid #dc3545;
            color: #dc3545;
            font-family: var(--bs-font-monospace);
            font-size: 0.875rem;
        }
        .compiler-warning-widget {
            padding: 0.25rem 0.5rem;
            margin: 0.25rem 0;
            background-color: rgba(255, 193, 7, 0.1);
            border-left: 3px solid #ffc107;
            color: #856404;
            font-family: var(--bs-font-monospace);
            font-size: 0.875rem;
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