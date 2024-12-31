const monacoEditor = {
    initialized: false,
    instances: new Map(),
    loaderPromise: null,

    async initialize(elementId, options = {}) {
        try {
            const editorElement = document.getElementById(elementId);
            if (!editorElement) {
                throw new Error(`Editor element with id '${elementId}' not found`);
            }

            const initialValue = options.value || this.getDefaultCode(options.language || 'cpp');
            options.value = initialValue;

            this.dispose(elementId);
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
            this.loaderPromise = new Promise((resolve, reject) => {
                try {
                    if (window.monaco && !window._monacoLoaded) {
                        window._monacoLoaded = true;
                        resolve();
                        return;
                    }

                    const script = document.createElement('script');
                    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs/loader.min.js';
                    script.onload = () => {
                        require.config({
                            paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }
                        });
                        require(['vs/editor/editor.main'], () => {
                            window._monacoLoaded = true;
                            resolve();
                        });
                    };
                    script.onerror = (error) => reject(new Error('Failed to load Monaco Editor: ' + error.message));
                    document.head.appendChild(script);
                } catch (error) {
                    reject(error);
                }
            });
        }
        return this.loaderPromise;
    },

    createEditor(elementId, options) {
        try {
            const defaultOptions = {
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
                folding: true
            };

            const editorInstance = monaco.editor.create(
                document.getElementById(elementId), 
                { ...defaultOptions, ...options }
            );

            this.instances.set(elementId, editorInstance);
            this.setupEditorEventHandlers(editorInstance, elementId);
            this.initialized = true;

            return editorInstance;
        } catch (error) {
            console.error('Editor creation error:', error);
            this.showErrorMessage(error);
            throw error;
        }
    },

    setupEditorEventHandlers(editorInstance, elementId) {
        let changeTimeout;
        const disposables = [];

        disposables.push(
            editorInstance.onDidChangeModelContent(() => {
                if (changeTimeout) clearTimeout(changeTimeout);
                changeTimeout = setTimeout(() => this.onContentChanged(editorInstance), 300);
            }),
            editorInstance.onDidBlurEditorText(() => {
                this.saveEditorState(elementId, editorInstance.getValue());
            })
        );

        this.instances.set(elementId + '_disposables', disposables);
        this.setupResizeHandler(editorInstance, elementId);
    },

    setupResizeHandler(editorInstance, elementId) {
        const resizeHandler = () => {
            if (editorInstance) editorInstance.layout();
        };
        window.addEventListener('resize', resizeHandler);
        this.instances.set(elementId + '_resize', resizeHandler);
    },

    dispose(elementId) {
        const instance = this.instances.get(elementId);
        if (instance) {
            const disposables = this.instances.get(elementId + '_disposables') || [];
            disposables.forEach(d => d.dispose());

            const resizeHandler = this.instances.get(elementId + '_resize');
            if (resizeHandler) {
                window.removeEventListener('resize', resizeHandler);
            }

            instance.dispose();
            this.instances.delete(elementId);
            this.instances.delete(elementId + '_disposables');
            this.instances.delete(elementId + '_resize');
        }
    },

    getDefaultCode(language) {
        const templates = {
            cpp: `#include <iostream>

int main() {
    std::cout << "Bonjour le monde!" << std::endl;
    return 0;
}`,
            csharp: `using System;

class Program {
    static void Main() {
        Console.WriteLine("Bonjour le monde!");
    }
}`
        };
        return templates[language] || '';
    },

    showNotification(type, message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show notification-toast`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alertDiv);
        setTimeout(() => alertDiv.remove(), 5000);
    },
    showErrorMessage(error) {
        const errorContainer = document.getElementById('errorContainer');
        if (errorContainer) {
            errorContainer.style.display = 'block';
            errorContainer.innerHTML = `
                <div class="alert alert-danger">
                    <h6 class="mb-2">
                        <i class="bi bi-exclamation-triangle-fill"></i> Erreur d'initialisation
                    </h6>
                    <p class="mb-0">${error.message}</p>
                    <button class="btn btn-outline-danger btn-sm mt-2" onclick="location.reload()">
                        <i class="bi bi-arrow-clockwise"></i> Rafraîchir la page
                    </button>
                </div>
            `;
        }
    }
};

window.monacoEditor = monacoEditor;

document.addEventListener('DOMContentLoaded', async () => {
    const editorElement = document.getElementById('editor');
    if (!editorElement) return;

    try {
        const editor = await monacoEditor.initialize('editor', {
            value: editorElement.getAttribute('data-initial-value') || '',
            language: editorElement.getAttribute('data-language') || 'cpp'
        });

        if (editor) {
            setupEditorControls(editor);
        }
    } catch (error) {
        console.error('Editor initialization failed:', error);
        showErrorMessage(error);
    }
});

function setupEditorControls(editor) {
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', (e) => {
            const language = e.target.value;
            monaco.editor.setModelLanguage(editor.getModel(), language);
            loadSavedContent(editor, language);
        });
    }

    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', executeCode);
    }

    const shareButton = document.getElementById('shareButton');
    if (shareButton) {
        shareButton.addEventListener('click', () => shareCode(editor, shareButton));
    }
}

function loadSavedContent(editor, language) {
    const savedContent = localStorage.getItem(`editor_${language}_content`);
    editor.setValue(savedContent || monacoEditor.getDefaultCode(language));
}


window.addEventListener('beforeunload', () => {
    for (const [elementId] of monacoEditor.instances) {
        if (!elementId.includes('_')) {
            monacoEditor.dispose(elementId);
        }
    }
});