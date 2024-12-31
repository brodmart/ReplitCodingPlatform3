require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }});
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

const monacoEditor = {
    initialized: false,
    instances: new Map(),
    loaderPromise: null,

    async initialize(elementId, options = {}) {
        if (!document.getElementById(elementId)) return null;
        
        if (window.monaco) {
            return this.createEditor(elementId, options);
        }
        
        try {
            await this.loadMonaco();
            return this.createEditor(elementId, options);
        } catch (error) {
            console.error('Editor initialization error:', error);
            this.showErrorMessage(error);
            throw error;
        }
    },

    async loadMonaco() {
        if (!this.loaderPromise) {
            this.loaderPromise = new Promise((resolve) => {
                if (window.monaco) {
                    resolve(window.monaco);
                    return;
                }

                const script = document.createElement('script');
                script.src = "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs/loader.min.js";
                script.onload = () => {
                    require.config({
                        paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }
                    });
                    require(['vs/editor/editor.main'], () => {
                        resolve(window.monaco);
                    });
                };
                document.head.appendChild(script);
            });
        }
        return this.loaderPromise;
    },

    createEditor(elementId, options) {
        const editorElement = document.getElementById(elementId);
        if (!editorElement) return null;

        const defaultOptions = {
            value: options.value || this.getDefaultCode(options.language || 'cpp'),
            language: options.language || 'cpp',
            theme: 'vs-dark',
            minimap: { enabled: false },
            automaticLayout: true,
            fontSize: 14
        };

        const editor = monaco.editor.create(editorElement, defaultOptions);
        this.instances.set(elementId, editor);
        window.codeEditor = editor;
        return editor;
    },

    getDefaultCode(language) {
        const templates = {
            cpp: '#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << "Bonjour le monde!" << endl;\n    return 0;\n}',
            csharp: 'using System;\n\nclass Program\n{\n    static void Main()\n    {\n        Console.WriteLine("Bonjour le monde!");\n    }\n}'
        };
        return templates[language] || templates.cpp;
    },

    showErrorMessage(error) {
        const errorContainer = document.getElementById('errorContainer');
        if (errorContainer) {
            errorContainer.innerHTML = `<div class="alert alert-danger">Editor error: ${error.message}</div>`;
        }
    }
};

window.monacoEditor = monacoEditor;

document.addEventListener('DOMContentLoaded', async () => {
    const editorElement = document.getElementById('editor');
    if (!editorElement) return;

    try {
        const language = editorElement.getAttribute('data-language') || 'cpp';
        const initialValue = editorElement.getAttribute('data-initial-value') || '';
        const editor = await monacoEditor.initialize('editor', { 
            language,
            value: initialValue || monacoEditor.getDefaultCode(language)
        });
        
        if (editor) {
            const languageSelect = document.getElementById('languageSelect');
            if (languageSelect) {
                languageSelect.addEventListener('change', () => {
                    const newLanguage = languageSelect.value;
                    monaco.editor.setModelLanguage(editor.getModel(), newLanguage);
                    if (editor && monacoEditor) {
                        editor.setValue(monacoEditor.getDefaultCode(newLanguage));
                    } else {
                        console.error('Editor not properly initialized');
                    }
                });
            }

            const runButton = document.getElementById('runButton');
            if (runButton) {
                runButton.addEventListener('click', executeCode);
            }
        }
    } catch (error) {
        console.error('Editor initialization failed:', error);
    }
});

async function executeCode() {
    const editor = window.codeEditor;
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