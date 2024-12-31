let editor;
const monacoEditor = {
    initialize: function(elementId, options = {}) {
        return new Promise((resolve, reject) => {
            require.config({
                paths: {
                    'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs'
                }
            });

            require(['vs/editor/editor.main'], function() {
                try {
                    const defaultOptions = {
                        value: options.value || monacoEditor.getDefaultCode(options.language || 'cpp'),
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

                    // Create editor instance
                    editor = monaco.editor.create(document.getElementById(elementId), {
                        ...defaultOptions,
                        ...options
                    });

                    // Store editor instance globally
                    window.codeEditor = editor;
                    resolve(editor);
                } catch (error) {
                    console.error('Editor initialization error:', error);
                    reject(error);
                }
            });
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
    }
};

// Make monacoEditor globally available
window.monacoEditor = monacoEditor;

// Set up event handlers
const languageSelect = document.getElementById('languageSelect');
if (languageSelect) {
    languageSelect.addEventListener('change', function(e) {
        const language = e.target.value;
        monaco.editor.setModelLanguage(editor.getModel(), language);
        monacoEditor.setValue(monacoEditor.getDefaultCode(language));
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

async function executeCode() {
    const runButton = document.getElementById('runButton');
    const output = document.getElementById('output');
    const language = document.getElementById('languageSelect').value;

    if (!runButton || !output) return;

    try {
        runButton.disabled = true;
        runButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Exécution...';

        const response = await fetch('/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                code: monacoEditor.getValue(),
                language: language
            })
        });

        const result = await response.json();

        if (result.error) {
            output.innerHTML = formatError(result.error);
        } else {
            output.innerHTML = result.output || 'Programme exécuté avec succès sans sortie.';
        }
    } catch (error) {
        output.innerHTML = formatError(error.message);
    } finally {
        runButton.disabled = false;
        runButton.innerHTML = '<i class="bi bi-play-fill"></i> Exécuter';
    }
}

function formatError(error) {
    return `<div class="alert alert-danger">
        <strong>Erreur:</strong><br>
        <pre class="mb-0">${error}</pre>
    </div>`;
}

async function shareCode() {
    const shareButton = document.getElementById('shareButton');
    if (!shareButton) return;

    const code = monacoEditor.getValue();
    const language = document.getElementById('languageSelect').value;

    try {
        shareButton.disabled = true;
        shareButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Partage...';

        const response = await fetch('/share', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                code: code,
                language: language
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

// Handle window resizing
window.addEventListener('resize', function() {
    if (editor) {
        editor.layout();
    }
});