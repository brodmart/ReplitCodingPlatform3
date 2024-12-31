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

    // Add error handling utilities
    handleExecutionError: function(error) {
        const output = document.getElementById('output');
        if (output) {
            output.innerHTML = this.formatError(error.message || 'Une erreur inattendue est survenue');
        }
    },

    formatError: function(error) {
        return `<div class="alert alert-danger">
            <strong>Erreur:</strong><br>
            <pre class="mb-0">${error}</pre>
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
            output.innerHTML = monacoEditor.formatError(result.error);
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