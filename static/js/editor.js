let editor;

require.config({
    paths: {
        'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs'
    }
});

// Initialize Monaco editor with language features
require(['vs/editor/editor.main'], function() {
    // Configure language features
    monaco.languages.typescript.javascriptDefaults.setDiagnosticsOptions({
        noSemanticValidation: true,
        noSyntaxValidation: true
    });

    // Create editor instance
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
        // Enhanced editor features
        formatOnType: true,
        formatOnPaste: true,
        autoIndent: 'full',
        bracketPairColorization: {
            enabled: true
        },
        // Language specific features
        suggestOnTriggerCharacters: true,
        wordBasedSuggestions: true,
        // Code folding
        folding: true,
        foldingStrategy: 'indentation',
        // Line numbers
        lineNumbers: true,
        lineDecorationsWidth: 0,
        // Rendering
        renderControlCharacters: true,
        roundedSelection: false,
        // Tab completion
        tabCompletion: 'on',
        // Auto closing
        autoClosingBrackets: 'always',
        autoClosingQuotes: 'always'
    });

    // Language change handler with improved state management
    document.getElementById('languageSelect').addEventListener('change', function(e) {
        const language = e.target.value;
        const currentState = editor.saveViewState();

        // Update editor model with new language
        const model = editor.getModel();
        monaco.editor.setModelLanguage(model, language);

        // Update content with default code while preserving state
        editor.setValue(getDefaultCode(language));

        // Restore view state if possible
        if (currentState) {
            editor.restoreViewState(currentState);
        }

        editor.focus();
    });

    // Run button handler
    document.getElementById('runButton').addEventListener('click', executeCode);

    // Add share button handler
    document.getElementById('shareButton').addEventListener('click', shareCode);
});

function getDefaultCode(language) {
    if (language === 'cpp') {
        return `#include <iostream>

int main() {
    std::cout << "Hello, World!" << std::endl;
    return 0;
}`;
    } else if (language === 'csharp') {
        return `using System;

class Program {
    static void Main() {
        Console.WriteLine("Hello, World!");
    }
}`;
    }
}

async function executeCode() {
    const runButton = document.getElementById('runButton');
    const output = document.getElementById('output');
    const language = document.getElementById('languageSelect').value;

    try {
        runButton.disabled = true;
        runButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...';

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
            output.innerHTML = `<span style="color: var(--bs-danger)">Error:\n${result.error}</span>`;
        } else {
            output.innerHTML = result.output || 'Program executed successfully with no output.';
        }
    } catch (error) {
        output.innerHTML = `<span style="color: var(--bs-danger)">Error: ${error.message}</span>`;
    } finally {
        runButton.disabled = false;
        runButton.innerHTML = '<i class="bi bi-play-fill"></i> Run';
    }
}

async function shareCode() {
    const shareButton = document.getElementById('shareButton');
    const code = editor.getValue();
    const language = document.getElementById('languageSelect').value;

    try {
        shareButton.disabled = true;
        shareButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Sharing...';

        const response = await fetch('/share', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                code: code,
                language: language,
                title: 'Shared Code',
                description: '',
                is_public: true
            })
        });

        const result = await response.json();

        if (result.error) {
            alert('Error sharing code: ' + result.error);
        } else {
            // Copy share URL to clipboard
            await navigator.clipboard.writeText(result.share_url);
            alert('Code shared successfully! Link copied to clipboard.');
        }
    } catch (error) {
        alert('Error sharing code: ' + error.message);
    } finally {
        shareButton.disabled = false;
        shareButton.innerHTML = '<i class="bi bi-share"></i> Share';
    }
}

// Handle window resize
window.addEventListener('resize', function() {
    if (editor) {
        editor.layout();
    }
});