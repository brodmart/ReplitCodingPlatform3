let editor;
const monacoEditor = {
    // Keep track of initialization state
    initialized: false,

    initialize: function(elementId, options = {}) {
        // Prevent duplicate initialization
        if (this.initialized) {
            console.warn('Monaco Editor already initialized');
            return Promise.resolve(editor);
        }

        return new Promise((resolve, reject) => {
            // Only configure require.js once
            if (!window.requirejs) {
                require.config({
                    paths: {
                        'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs'
                    }
                });
            }

            try {
                require(['vs/editor/editor.main'], () => {
                    const defaultOptions = {
                        value: options.value || this.getDefaultCode(options.language || 'cpp'),
                        language: options.language || 'cpp',
                        theme: 'vs-dark',
                        minimap: { enabled: false },
                        automaticLayout: true,
                        fontSize: 14,
                        scrollBeyondLastLine: false,
                        renderWhitespace: 'selection',
                        padding: { top: 10, bottom: 10 },
                        formatOnType: true,
                        formatOnPaste: true,
                        autoIndent: 'full',
                        bracketPairColorization: { enabled: true },
                        suggestOnTriggerCharacters: true,
                        wordBasedSuggestions: 'on',
                        folding: true,
                        foldingStrategy: 'indentation',
                        lineNumbers: true,
                        lineDecorationsWidth: 0,
                        renderControlCharacters: true,
                        roundedSelection: false,
                        tabCompletion: 'on',
                        autoClosingBrackets: 'always',
                        autoClosingQuotes: 'always'
                    };

                    const editorElement = document.getElementById(elementId);
                    if (!editorElement) {
                        throw new Error(`Editor element with id '${elementId}' not found`);
                    }

                    // Create editor instance
                    editor = monaco.editor.create(editorElement, {
                        ...defaultOptions,
                        ...options
                    });

                    // Store editor instance globally and mark as initialized
                    window.codeEditor = editor;
                    this.initialized = true;

                    // Add resize handler
                    window.addEventListener('resize', () => {
                        if (editor) {
                            editor.layout();
                        }
                    });

                    resolve(editor);
                });
            } catch (error) {
                console.error('Editor initialization error:', error);
                reject(error);
            }
        });
    },

    getValue: function() {
        return editor ? editor.getValue() : '';
    },

    setValue: function(value) {
        if (editor) {
            editor.setValue(value);
        }
    },

    getDefaultCode: function(language) {
        if (language === 'cpp') {
            return `#include <iostream>\n\nint main() {\n    std::cout << "Bonjour le monde!" << std::endl;\n    return 0;\n}`;
        } else if (language === 'csharp') {
            return `using System;\n\nclass Program {\n    static void Main() {\n        Console.WriteLine("Bonjour le monde!");\n    }\n}`;
        }
        return '';
    },

    // Enhanced error handling utilities
    handleExecutionError: function(error) {
        const output = document.getElementById('output');
        if (output) {
            if (typeof error === 'object' && error.error_details) {
                output.innerHTML = this.formatErrorWithDetails(error);
            } else {
                output.innerHTML = this.formatError(error.message || 'Une erreur inattendue est survenue');
            }
        }
    },

    formatErrorWithDetails: function(error) {
        const details = error.error_details;
        const errorType = details.type || 'unknown';

        switch (errorType) {
            case 'error':
                return this.formatCompilerError(error);
            case 'runtime_error':
                return this.formatRuntimeError(error);
            case 'timeout':
                return this.formatTimeoutError(error);
            default:
                return this.formatGenericError(error);
        }
    },

    formatCompilerError: function(error) {
        const details = error.error_details;
        let suggestion = '';

        // Add specific suggestions for common errors
        if (error.full_error && error.full_error.includes('std::end')) {
            suggestion = `
                <div class="alert alert-info mt-2">
                    <i class="bi bi-lightbulb"></i>
                    Conseil: Vous voulez probablement utiliser <code>std::endl</code> au lieu de <code>std::end</code>
                    pour ajouter un retour à la ligne.
                </div>`;
        }

        return `
            <div class="alert alert-danger">
                <h5 class="alert-heading">
                    <i class="bi bi-exclamation-triangle"></i> 
                    Erreur de Compilation
                    ${details.line ? `<small class="text-muted">(Ligne ${details.line})</small>` : ''}
                </h5>
                <hr>
                <p class="mb-2"><strong>${details.message}</strong></p>
                ${suggestion}
                <div class="mt-3">
                    <small class="text-muted">
                        Vérifiez:
                        <ul class="mt-1 mb-0">
                            <li>La syntaxe de votre code (points-virgules, parenthèses)</li>
                            <li>Les noms des fonctions et variables</li>
                            <li>Les bibliothèques incluses</li>
                        </ul>
                    </small>
                </div>
            </div>`;
    },

    formatRuntimeError: function(error) {
        return `
            <div class="alert alert-danger">
                <h5 class="alert-heading">
                    <i class="bi bi-exclamation-circle"></i> 
                    Erreur d'Exécution
                </h5>
                <hr>
                <p class="mb-2">${error.error_details.message}</p>
                <div class="mt-2">
                    <small class="text-muted">
                        Cette erreur s'est produite pendant l'exécution de votre programme.
                        Vérifiez la logique de votre code et les valeurs utilisées.
                    </small>
                </div>
            </div>`;
    },

    formatTimeoutError: function(error) {
        return `
            <div class="alert alert-warning">
                <h5 class="alert-heading">
                    <i class="bi bi-clock-history"></i> 
                    Timeout d'Exécution
                </h5>
                <hr>
                <p class="mb-2">${error.error}</p>
                <div class="mt-2">
                    <small class="text-muted">
                        Votre programme a dépassé la limite de temps d'exécution.
                        Vérifiez s'il y a des boucles infinies ou des opérations trop longues.
                    </small>
                </div>
            </div>`;
    },

    formatGenericError: function(error) {
        return `
            <div class="alert alert-danger">
                <h5 class="alert-heading">
                    <i class="bi bi-exclamation-circle"></i> 
                    Erreur Système
                </h5>
                <hr>
                <p class="mb-2">${error.error}</p>
                <div class="mt-2">
                    <small class="text-muted">
                        Une erreur inattendue s'est produite.
                        Si le problème persiste, contactez le support technique.
                    </small>
                </div>
            </div>`;
    }
};

// Make monacoEditor globally available
window.monacoEditor = monacoEditor;

async function executeCode() {
    const runButton = document.getElementById('runButton');
    const output = document.getElementById('output');
    const languageSelect = document.getElementById('languageSelect');

    if (!runButton || !output || !languageSelect || !window.codeEditor) {
        console.error('Required elements not found');
        return;
    }

    try {
        runButton.disabled = true;
        runButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Exécution...';

        const response = await fetch('/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                code: window.codeEditor.getValue(),
                language: languageSelect.value
            })
        });

        const result = await response.json();

        if (result.error) {
            output.innerHTML = monacoEditor.formatErrorWithDetails(result);
        } else {
            output.innerHTML = result.output || 'Programme exécuté avec succès sans sortie.';
        }
    } catch (error) {
        monacoEditor.handleExecutionError(error);
    } finally {
        runButton.disabled = false;
        runButton.innerHTML = '<i class="bi bi-play-fill"></i> Exécuter';
    }
}

async function shareCode() {
    const shareButton = document.getElementById('shareButton');
    if (!shareButton || !window.codeEditor) {
        console.error('Required elements not found');
        return;
    }

    try {
        shareButton.disabled = true;
        shareButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Partage...';

        const response = await fetch('/share', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                code: window.codeEditor.getValue(),
                language: document.getElementById('languageSelect').value
            })
        });

        const result = await response.json();

        if (result.error) {
            showNotification('error', 'Erreur lors du partage du code: ' + result.error);
        } else {
            showNotification('success', 'Code partagé avec succès!');
        }
    } catch (error) {
        showNotification('error', 'Erreur lors du partage du code: ' + error.message);
    } finally {
        shareButton.disabled = false;
        shareButton.innerHTML = '<i class="bi bi-share"></i> Partager';
    }
}

function showNotification(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show notification-toast`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(alertDiv);
    setTimeout(() => alertDiv.remove(), 5000);
}

// Set up event handlers
const languageSelect = document.getElementById('languageSelect');
if (languageSelect) {
    languageSelect.addEventListener('change', function(e) {
        const language = e.target.value;
        if (editor) {
            monaco.editor.setModelLanguage(editor.getModel(), language);
            monacoEditor.setValue(monacoEditor.getDefaultCode(language));
        }
    });
}

const runButton = document.getElementById('runButton');
if (runButton) {
    runButton.addEventListener('click', executeCode);
}

const shareButton = document.getElementById('shareButton');
if (shareButton) {
    shareButton.addEventListener('click', shareCode);
}