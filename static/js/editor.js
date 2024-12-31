let editor;

require.config({
    paths: {
        'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs'
    }
});

require(['vs/editor/editor.main'], function() {
    // Define C++ language configuration
    monaco.languages.register({ id: 'cpp' });
    monaco.languages.setMonarchTokensProvider('cpp', {
        defaultToken: '',
        tokenPostfix: '.cpp',
        brackets: [
            { open: '{', close: '}', token: 'delimiter.curly' },
            { open: '[', close: ']', token: 'delimiter.square' },
            { open: '(', close: ')', token: 'delimiter.parenthesis' },
            { open: '<', close: '>', token: 'delimiter.angle' }
        ],
        keywords: [
            'class', 'namespace', 'template', 'struct', 'using',
            'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break',
            'continue', 'return', 'typedef', 'static', 'enum', 'union',
            'void', 'const', 'bool', 'int', 'float', 'double', 'char', 'unsigned',
            'signed', 'short', 'long', 'volatile', 'inline', 'virtual', 'public',
            'private', 'protected', 'friend', 'operator', 'explicit', 'extern',
            'register', 'mutable', 'asm', 'true', 'false', 'new', 'delete',
            'default', 'throw', 'try', 'catch', 'sizeof', 'dynamic_cast',
            'static_cast', 'const_cast', 'reinterpret_cast', 'typeid', 'typename',
            'this', 'template', 'nullptr', 'goto', 'auto'
        ],
        operators: [
            '=', '>', '<', '!', '~', '?', ':',
            '==', '<=', '>=', '!=', '&&', '||', '++', '--',
            '+', '-', '*', '/', '&', '|', '^', '%', '<<',
            '>>', '>>>', '+=', '-=', '*=', '/=', '&=', '|=',
            '^=', '%=', '<<=', '>>=', '>>>='
        ],
        symbols: /[=><!~?:&|+\-*\/\^%]+/,
        escapes: /\\(?:[abfnrtv\\"']|x[0-9A-Fa-f]{1,4}|u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8})/,
        tokenizer: {
            root: [
                [/[a-z_$][\w$]*/, {
                    cases: {
                        '@keywords': 'keyword',
                        '@default': 'identifier'
                    }
                }],
                [/[A-Z][\w\$]*/, 'type.identifier'],
                { include: '@whitespace' },
                [/[{}()\[\]]/, '@brackets'],
                [/[<>](?!@symbols)/, '@brackets'],
                [/@symbols/, {
                    cases: {
                        '@operators': 'operator',
                        '@default': ''
                    }
                }],
                [/\d*\.\d+([eE][\-+]?\d+)?/, 'number.float'],
                [/0[xX][0-9a-fA-F]+/, 'number.hex'],
                [/\d+/, 'number'],
                [/[;,.]/, 'delimiter'],
                [/"([^"\\]|\\.)*$/, 'string.invalid'],
                [/"/, { token: 'string.quote', bracket: '@open', next: '@string' }],
                [/'[^\\']'/, 'string'],
                [/(')(@escapes)(')/, ['string', 'string.escape', 'string']],
                [/'/, 'string.invalid']
            ],
            comment: [
                [/[^\/*]+/, 'comment'],
                [/\/\*/, 'comment', '@push'],
                ["\\*/", 'comment', '@pop'],
                [/[\/*]/, 'comment']
            ],
            string: [
                [/[^\\"]+/, 'string'],
                [/@escapes/, 'string.escape'],
                [/\\./, 'string.escape.invalid'],
                [/"/, { token: 'string.quote', bracket: '@close', next: '@pop' }]
            ],
            whitespace: [
                [/[ \t\r\n]+/, 'white'],
                [/\/\*/, 'comment', '@comment'],
                [/\/\/.*$/, 'comment'],
            ],
        }
    });

    // Create editor instance
    editor = monaco.editor.create(document.getElementById('editor'), {
        value: getDefaultCode('cpp'),
        language: 'cpp',
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
    });

    // Set up event handlers
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', function(e) {
            const language = e.target.value;
            monaco.editor.setModelLanguage(editor.getModel(), language);
            editor.setValue(getDefaultCode(language));
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

function formatError(error) {
    return `<div class="alert alert-danger">
        <strong>Erreur:</strong><br>
        <pre class="mb-0">${error}</pre>
    </div>`;
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