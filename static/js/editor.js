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
            this.loaderPromise = new Promise((resolve) => {
                if (window.monaco) {
                    resolve(window.monaco);
                    return;
                }

                // Prevent duplicate module definitions
                if (!window.require) {
                    const script = document.createElement('script');
                    script.src = "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs/loader.min.js";
                    script.onload = () => {
                        require.config({
                            paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' }
                        });
                        require(['vs/editor/editor.main'], () => {
                            resolve(window.monaco);
                        });
                    };
                    document.head.appendChild(script);
                } else {
                    // If require is already defined, just load Monaco
                    require(['vs/editor/editor.main'], () => {
                        resolve(window.monaco);
                    });
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
                folding: true,
                fixedOverflowWidgets: true // Fix for suggestion widget overflow
            };

            const editorInstance = monaco.editor.create(
                document.getElementById(elementId), 
                { ...defaultOptions, ...options }
            );

            this.instances.set(elementId, editorInstance);
            this.setupEditorEventHandlers(editorInstance, elementId);
            this.initialized = true;

            // Add error boundary integration
            if (window.errorBoundary) {
                editorInstance.onDidChangeModelContent(() => {
                    try {
                        this.saveEditorState(elementId, editorInstance.getValue());
                    } catch (error) {
                        window.errorBoundary.handleError({
                            type: 'editor_error',
                            message: 'Failed to save editor state',
                            error: error
                        });
                    }
                });
            }

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

        // Handle content changes with debouncing
        disposables.push(
            editorInstance.onDidChangeModelContent(() => {
                if (changeTimeout) clearTimeout(changeTimeout);
                changeTimeout = setTimeout(() => {
                    this.saveEditorState(elementId, editorInstance.getValue());
                    this.onContentChanged(editorInstance);
                }, 300);
            })
        );

        this.instances.set(elementId + '_disposables', disposables);
        this.setupResizeHandler(editorInstance, elementId);
    },

    setupResizeHandler(editorInstance, elementId) {
        const resizeHandler = () => {
            if (editorInstance) {
                try {
                    editorInstance.layout();
                } catch (error) {
                    console.error('Editor resize error:', error);
                }
            }
        };
        window.addEventListener('resize', resizeHandler);
        this.instances.set(elementId + '_resize', resizeHandler);
    },

    dispose(elementId) {
        const instance = this.instances.get(elementId);
        if (instance) {
            try {
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
            } catch (error) {
                console.error('Error disposing editor:', error);
            }
        }
    },

    getDefaultCode(language) {
        const templates = {
            cpp: `#include <iostream>\n\nint main() {\n    std::cout << "Bonjour le monde!" << std::endl;\n    return 0;\n}`,
            csharp: `using System;\n\nclass Program {\n    static void Main() {\n        Console.WriteLine("Bonjour le monde!");\n    }\n}`,
            python: `print("Bonjour le monde!")`,
            javascript: `console.log("Bonjour le monde!");`
        };
        return templates[language] || '';
    },

    saveEditorState(elementId, content) {
        try {
            localStorage.setItem(`editor_${elementId}`, content);
        } catch (error) {
            console.error('Failed to save editor state:', error);
            if (window.errorBoundary) {
                window.errorBoundary.handleError({
                    type: 'editor_error',
                    message: 'Failed to save editor state',
                    error: error
                });
            }
        }
    },

    onContentChanged(editorInstance) {
        // This can be extended to handle content changes
        console.log('Editor content changed');
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
                </div>
            `;
        }
    }
};

// Make monacoEditor globally accessible
window.monacoEditor = monacoEditor;

// Initialize editor when DOM is loaded with error handling
document.addEventListener('DOMContentLoaded', async () => {
    const editorElement = document.getElementById('editor');
    if (!editorElement) return;

    try {
        const editor = await monacoEditor.initialize('editor', {
            value: editorElement.getAttribute('data-initial-value') || '',
            language: editorElement.getAttribute('data-language') || 'cpp'
        });

        if (editor) {
            window.codeEditor = editor;
            setupEditorControls();
        }
    } catch (error) {
        console.error('Editor initialization failed:', error);
        monacoEditor.showErrorMessage(error);
        if (window.errorBoundary) {
            window.errorBoundary.handleError({
                type: 'editor_error',
                message: 'Failed to initialize editor',
                error: error
            });
        }
    }
});

// Setup editor controls
function setupEditorControls() {
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', executeCode);
    }
}

async function executeCode() {
    const runButton = document.getElementById('runButton');
    const output = document.getElementById('output');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

    if (!window.codeEditor) {
        console.error('Editor not initialized');
        return;
    }

    if (!csrfToken) {
        console.error('CSRF token not found');
        if (output) {
            output.innerHTML = '<pre class="error">Erreur: CSRF token manquant</pre>';
        }
        return;
    }

    try {
        runButton.disabled = true;
        if (loadingOverlay) loadingOverlay.classList.add('show');

        const response = await fetch('/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                code: window.codeEditor.getValue(),
                language: document.getElementById('editor').getAttribute('data-language') || 'cpp'
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        if (output) {
            output.innerHTML = `<pre class="${result.success ? 'success' : 'error'}">${result.output || result.error}</pre>`;
        }
    } catch (error) {
        if (output) {
            output.innerHTML = `<pre class="error">Erreur d'exécution: ${error.message}</pre>`;
        }
        if (window.errorBoundary) {
            window.errorBoundary.handleError({
                type: 'execution_error',
                message: 'Failed to execute code',
                error: error
            });
        }
    } finally {
        runButton.disabled = false;
        if (loadingOverlay) loadingOverlay.classList.remove('show');
    }
}