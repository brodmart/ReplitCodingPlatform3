
// Single editor instance
let editor = null;

// Initialize editor only once
async function initializeEditor(elementId, options = {}) {
    if (!document.getElementById(elementId)) return;
    
    try {
        const monaco = await loadMonaco();
        const defaultOptions = {
            value: options.value || getDefaultCode(options.language || 'cpp'),
            language: options.language || 'cpp',
            theme: 'vs-dark',
            minimap: { enabled: false },
            automaticLayout: true,
            fontSize: 14
        };

        editor = monaco.editor.create(document.getElementById(elementId), defaultOptions);
        window.codeEditor = editor;
        
        setupLanguageSelect(editor);
        setupRunButton();
        
        return editor;
    } catch (error) {
        console.error('Editor initialization error:', error);
        showErrorMessage(error);
    }
}

function loadMonaco() {
    return new Promise((resolve) => {
        if (window.monaco) {
            resolve(window.monaco);
            return;
        }

        require(['vs/editor/editor.main'], () => {
            resolve(window.monaco);
        });
    });
}

function getDefaultCode(language) {
    const templates = {
        cpp: '#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << "Bonjour le monde!" << endl;\n    return 0;\n}',
        csharp: 'using System;\n\nclass Program\n{\n    static void Main()\n    {\n        Console.WriteLine("Bonjour le monde!");\n    }\n}'
    };
    return templates[language] || templates.cpp;
}

function setupLanguageSelect(editor) {
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', () => {
            const newLanguage = languageSelect.value;
            if (editor) {
                monaco.editor.setModelLanguage(editor.getModel(), newLanguage);
                editor.setValue(getDefaultCode(newLanguage));
            }
        });
    }
}

function setupRunButton() {
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', executeCode);
    }
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

function showErrorMessage(error) {
    const errorContainer = document.getElementById('errorContainer');
    if (errorContainer) {
        errorContainer.innerHTML = `<div class="alert alert-danger">Editor error: ${error.message}</div>`;
    }
}

// Initialize editor when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const editorElement = document.getElementById('editor');
    if (editorElement) {
        const language = editorElement.getAttribute('data-language') || 'cpp';
        const initialValue = editorElement.getAttribute('data-initial-value') || '';
        initializeEditor('editor', {
            language,
            value: initialValue || getDefaultCode(language)
        });
    }
});
