
// Load Monaco Editor from CDN
require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }});

window.MonacoEnvironment = {
    getWorkerUrl: function() {
        return `data:text/javascript;charset=utf-8,${encodeURIComponent(`
            self.MonacoEnvironment = {
                baseUrl: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/'
            };
            importScripts('https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs/base/worker/workerMain.js');`
        )}`;
    }
};

let editor = null;

function initMonaco() {
    require(['vs/editor/editor.main'], function() {
        const editorElement = document.getElementById('editor');
        if (!editorElement) return;

        const language = editorElement.getAttribute('data-language') || 'cpp';
        const initialValue = editorElement.getAttribute('data-initial-value') || getDefaultCode(language);

        editor = monaco.editor.create(editorElement, {
            value: initialValue,
            language: language,
            theme: 'vs-dark',
            minimap: { enabled: false },
            automaticLayout: true,
            fontSize: 14
        });
        window.codeEditor = editor;

        // Setup language selector if it exists
        const languageSelect = document.getElementById('languageSelect');
        if (languageSelect) {
            languageSelect.addEventListener('change', function() {
                const newLanguage = languageSelect.value;
                monaco.editor.setModelLanguage(editor.getModel(), newLanguage);
                editor.setValue(getDefaultCode(newLanguage));
            });
        }
    });
}

function getDefaultCode(language) {
    const templates = {
        cpp: '#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << "Hello World!" << endl;\n    return 0;\n}',
        csharp: 'using System;\n\nclass Program\n{\n    static void Main()\n    {\n        Console.WriteLine("Hello World!");\n    }\n}'
    };
    return templates[language] || templates.cpp;
}

async function executeCode() {
    if (!editor) {
        console.error('Editor not initialized');
        return;
    }

    const output = document.getElementById('output');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const languageSelect = document.getElementById('languageSelect');
    
    if (!csrfToken) {
        if (output) output.innerHTML = '<pre class="error">Erreur: CSRF token manquant</pre>';
        return;
    }

    try {
        const response = await fetch('/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                code: editor.getValue(),
                language: languageSelect ? languageSelect.value : 'cpp'
            })
        });

        const result = await response.json();
        if (output) {
            output.innerHTML = `<pre class="${result.success ? 'success' : 'error'}">${result.output || result.error}</pre>`;
        }
    } catch (error) {
        if (output) {
            output.innerHTML = `<pre class="error">Erreur d'exécution: ${error.message}</pre>`;
        }
    }
}

document.addEventListener('DOMContentLoaded', initMonaco);
