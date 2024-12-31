let editor;

require.config({
    paths: {
        'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs'
    }
});

require(['vs/editor/editor.main'], function() {
    // Configure C++ language features
    monaco.languages.cpp = monaco.languages.cpp || {};
    monaco.languages.cpp.languageConfiguration = {
        comments: {
            lineComment: '//',
            blockComment: ['/*', '*/']
        },
        brackets: [
            ['{', '}'],
            ['[', ']'],
            ['(', ')']
        ],
        autoClosingPairs: [
            { open: '{', close: '}' },
            { open: '[', close: ']' },
            { open: '(', close: ')' },
            { open: '"', close: '"' },
            { open: "'", close: "'" }
        ]
    };

    // Configure C# language features
    monaco.languages.csharp = monaco.languages.csharp || {};
    monaco.languages.csharp.languageConfiguration = {
        comments: {
            lineComment: '//',
            blockComment: ['/*', '*/']
        },
        brackets: [
            ['{', '}'],
            ['[', ']'],
            ['(', ')']
        ],
        autoClosingPairs: [
            { open: '{', close: '}' },
            { open: '[', close: ']' },
            { open: '(', close: ')' },
            { open: '"', close: '"' },
            { open: "'", close: "'" }
        ]
    };

    editor = monaco.editor.create(document.getElementById('editor'), {
        value: getDefaultCode('cpp'),
        language: 'cpp',
        theme: 'vs-dark',
        minimap: {
            enabled: false
        },
        automaticLayout: true,
        fontSize: 14,
        scrollBeyondLastLine: false,
        renderWhitespace: 'selection',
        padding: {
            top: 10,
            bottom: 10
        },
        formatOnType: true,
        formatOnPaste: true,
        autoIndent: 'full',
        bracketPairColorization: {
            enabled: true
        },
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
        autoClosingQuotes: 'always',
        snippets: true,
        suggest: {
            snippetsPreventQuickSuggestions: false
        },
        // Add intelligent code completion
        quickSuggestions: {
            other: true,
            comments: true,
            strings: true
        }
    });

    // Set up language change handler
    document.getElementById('languageSelect')?.addEventListener('change', function(e) {
        const language = e.target.value;
        const currentState = editor.saveViewState();
        const model = editor.getModel();
        monaco.editor.setModelLanguage(model, language);
        editor.setValue(getDefaultCode(language));
        if (currentState) {
            editor.restoreViewState(currentState);
        }
        editor.focus();
    });

    // Set up execution handler
    document.getElementById('runButton')?.addEventListener('click', executeCode);

    // Set up share handler
    document.getElementById('shareButton')?.addEventListener('click', shareCode);

    // Add real-time syntax validation
    let validationTimeout;
    editor.onDidChangeModelContent(() => {
        clearTimeout(validationTimeout);
        validationTimeout = setTimeout(validateSyntax, 500);
    });
});

function getDefaultCode(language) {
    if (language === 'cpp') {
        return `#include <iostream>

int main() {
    std::cout << "Bonjour le monde!" << std::endl;
    return 0;
}`;
    } else if (language === 'csharp') {
        return `using System;

class Program {
    static void Main() {
        Console.WriteLine("Bonjour le monde!");
    }
}`;
    }
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
                code: editor.getValue(),
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

async function shareCode() {
    const shareButton = document.getElementById('shareButton');
    if (!shareButton) return;

    const code = editor.getValue();
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
                language: language,
                title: 'Code Partagé',
                description: '',
                is_public: true
            })
        });

        const result = await response.json();

        if (result.error) {
            showNotification('error', 'Erreur lors du partage du code: ' + result.error);
        } else {
            await navigator.clipboard.writeText(result.share_url);
            showNotification('success', 'Code partagé avec succès! Lien copié dans le presse-papiers.');
        }
    } catch (error) {
        showNotification('error', 'Erreur lors du partage du code: ' + error.message);
    } finally {
        shareButton.disabled = false;
        shareButton.innerHTML = '<i class="bi bi-share"></i> Partager';
    }
}

function formatError(error) {
    return `<div class="alert alert-danger">
        <strong>Erreur:</strong><br>
        <pre class="mb-0">${error}</pre>
    </div>`;
}

function showNotification(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(alertDiv);
    setTimeout(() => alertDiv.remove(), 5000);
}

async function validateSyntax() {
    const code = editor.getValue();
    const language = document.getElementById('languageSelect').value;

    try {
        const response = await fetch('/validate_syntax', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ code, language })
        });

        const result = await response.json();
        updateEditorDecorations(result.errors || []);
    } catch (error) {
        console.error('Error validating syntax:', error);
    }
}

function updateEditorDecorations(errors) {
    const decorations = errors.map(error => ({
        range: new monaco.Range(
            error.line,
            error.column,
            error.line,
            error.column + (error.length || 1)
        ),
        options: {
            inlineClassName: 'squiggly-error',
            hoverMessage: { value: `${error.message_fr}\n${error.message_en}` }
        }
    }));

    editor.deltaDecorations([], decorations);
}

window.addEventListener('resize', function() {
    if (editor) {
        editor.layout();
    }
});