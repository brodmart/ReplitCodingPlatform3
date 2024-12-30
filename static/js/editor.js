let editor;

require.config({
    paths: {
        'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs'
    }
});

require(['vs/editor/editor.main'], function() {
    monaco.languages.typescript.javascriptDefaults.setDiagnosticsOptions({
        noSemanticValidation: true,
        noSyntaxValidation: true
    });

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
        wordBasedSuggestions: true,
        folding: true,
        foldingStrategy: 'indentation',
        lineNumbers: true,
        lineDecorationsWidth: 0,
        renderControlCharacters: true,
        roundedSelection: false,
        tabCompletion: 'on',
        autoClosingBrackets: 'always',
        autoClosingQuotes: 'always'
    });

    document.getElementById('languageSelect').addEventListener('change', function(e) {
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

    document.getElementById('runButton').addEventListener('click', executeCode);
    document.getElementById('shareButton').addEventListener('click', shareCode);
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
            output.innerHTML = `<span style="color: var(--bs-danger)">Erreur:\n${result.error}</span>`;
        } else {
            output.innerHTML = result.output || 'Programme exécuté avec succès sans sortie.';
        }
    } catch (error) {
        output.innerHTML = `<span style="color: var(--bs-danger)">Erreur: ${error.message}</span>`;
    } finally {
        runButton.disabled = false;
        runButton.innerHTML = '<i class="bi bi-play-fill"></i> Exécuter';
    }
}

async function shareCode() {
    const shareButton = document.getElementById('shareButton');
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
            alert('Erreur lors du partage du code: ' + result.error);
        } else {
            await navigator.clipboard.writeText(result.share_url);
            alert('Code partagé avec succès! Lien copié dans le presse-papiers.');
        }
    } catch (error) {
        alert('Erreur lors du partage du code: ' + error.message);
    } finally {
        shareButton.disabled = false;
        shareButton.innerHTML = '<i class="bi bi-share"></i> Partager';
    }
}

window.addEventListener('resize', function() {
    if (editor) {
        editor.layout();
    }
});