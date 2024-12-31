let editor;
const monacoEditor = {
    initialized: false,
    instances: new Map(),
    loaderPromise: null,

    initialize: function(elementId, options = {}) {
        return new Promise((resolve, reject) => {
            const editorElement = document.getElementById(elementId);
            if (!editorElement) {
                reject(new Error(`Editor element with id '${elementId}' not found`));
                return;
            }

            // Cleanup existing instance if present
            this.dispose(elementId);

            // Only load Monaco once
            if (!this.loaderPromise) {
                this.loaderPromise = new Promise((resolveLoader) => {
                    if (window.monaco && !window._monacoLoaded) {
                        window._monacoLoaded = true;
                        resolveLoader();
                        return;
                    }

                    const script = document.createElement('script');
                    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs/loader.min.js';
                    script.onload = () => {
                        require.config({
                            paths: {
                                'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs'
                            }
                        });
                        require(['vs/editor/editor.main'], resolveLoader);
                    };
                    script.onerror = (error) => reject(new Error('Failed to load Monaco Editor: ' + error.message));
                    document.head.appendChild(script);
                });
            }

            this.loaderPromise
                .then(() => {
                    const defaultOptions = {
                        value: options.value || this.getDefaultCode(options.language || 'cpp'),
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
                        autoClosingQuotes: 'always',
                        fastScrollSensitivity: 5,
                        scrollbar: {
                            useShadows: false,
                            verticalScrollbarSize: 10,
                            horizontalScrollbarSize: 10
                        }
                    };

                    const editorInstance = monaco.editor.create(editorElement, {
                        ...defaultOptions,
                        ...options
                    });

                    this.instances.set(elementId, editorInstance);
                    this.setupEditorEventHandlers(editorInstance, elementId);

                    editor = editorInstance;
                    this.initialized = true;

                    resolve(editorInstance);
                })
                .catch(reject);
        });
    },

    setupEditorEventHandlers: function(editorInstance, elementId) {
        let changeTimeout;
        const contentChangeHandler = () => {
            if (changeTimeout) clearTimeout(changeTimeout);
            changeTimeout = setTimeout(() => {
                this.onContentChanged(editorInstance);
            }, 300);
        };

        const disposables = [];
        disposables.push(
            editorInstance.onDidChangeModelContent(contentChangeHandler),
            editorInstance.onDidBlurEditorText(() => {
                this.saveEditorState(elementId, editorInstance.getValue());
            })
        );

        this.instances.set(elementId + '_disposables', disposables);

        let resizeTimeout;
        const resizeHandler = () => {
            if (resizeTimeout) clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                if (editorInstance) {
                    editorInstance.layout();
                }
            }, 100);
        };

        window.addEventListener('resize', resizeHandler);
        this.instances.set(elementId + '_resize', resizeHandler);
    },

    dispose: function(elementId) {
        const existingInstance = this.instances.get(elementId);
        if (existingInstance) {
            const disposables = this.instances.get(elementId + '_disposables') || [];
            disposables.forEach(d => d.dispose());

            const resizeHandler = this.instances.get(elementId + '_resize');
            if (resizeHandler) {
                window.removeEventListener('resize', resizeHandler);
            }

            existingInstance.dispose();

            this.instances.delete(elementId);
            this.instances.delete(elementId + '_disposables');
            this.instances.delete(elementId + '_resize');
        }
    },

    onContentChanged: function(editorInstance) {
        const value = editorInstance.getValue();
        // Implement auto-save or validation logic here if needed
    },

    saveEditorState: function(elementId, content) {
        try {
            localStorage.setItem(`editor_${elementId}_content`, content);
        } catch (e) {
            console.warn('Failed to save editor state:', e);
        }
    },

    loadEditorState: function(elementId) {
        try {
            return localStorage.getItem(`editor_${elementId}_content`);
        } catch (e) {
            console.warn('Failed to load editor state:', e);
            return null;
        }
    },

    getValue: function() {
        return editor ? editor.getValue() : '';
    },

    setValue: function(value) {
        if (editor) {
            const position = editor.getPosition();
            editor.setValue(value);
            if (position) {
                editor.setPosition(position);
            }
        }
    },

    getDefaultCode: function(language) {
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

    showNotification: function(type, message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show notification-toast`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alertDiv);
        setTimeout(() => alertDiv.remove(), 5000);
    }
};

// Make monacoEditor globally available
window.monacoEditor = monacoEditor;

// Initialize editor when document is ready
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const editorElement = document.getElementById('editor');
        if (!editorElement) {
            console.warn('Editor element not found, might be on a different page');
            return;
        }

        const editor = await monacoEditor.initialize('editor', {
            value: editorElement.getAttribute('data-initial-value') || '',
            language: editorElement.getAttribute('data-language') || 'cpp',
            readOnly: false,
            wordWrap: 'on',
            minimap: { enabled: true }
        });

        if (editor) {
            const languageSelect = document.getElementById('languageSelect');
            if (languageSelect) {
                languageSelect.addEventListener('change', function(e) {
                    const language = e.target.value;
                    monaco.editor.setModelLanguage(editor.getModel(), language);
                    const savedContent = monacoEditor.loadEditorState('editor_' + language);
                    if (savedContent) {
                        editor.setValue(savedContent);
                    } else {
                        editor.setValue(monacoEditor.getDefaultCode(language));
                    }
                });
            }

            const runButton = document.getElementById('runButton');
            if (runButton) {
                runButton.addEventListener('click', executeCode);
            }

            const shareButton = document.getElementById('shareButton');
            if (shareButton) {
                shareButton.addEventListener('click', async () => {
                    try {
                        shareButton.disabled = true;
                        shareButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Partage...';

                        const response = await fetch('/share', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                code: editor.getValue(),
                                language: document.getElementById('languageSelect')?.value || 'cpp'
                            })
                        });

                        const result = await response.json();

                        if (result.error) {
                            monacoEditor.showNotification('error', 'Erreur lors du partage du code: ' + result.error);
                        } else {
                            monacoEditor.showNotification('success', 'Code partagé avec succès!');
                        }
                    } catch (error) {
                        monacoEditor.showNotification('error', 'Erreur lors du partage du code: ' + error.message);
                    } finally {
                        shareButton.disabled = false;
                        shareButton.innerHTML = '<i class="bi bi-share"></i> Partager';
                    }
                });
            }
        }
    } catch (error) {
        console.error('Editor initialization failed:', error);
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
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    for (const [elementId] of monacoEditor.instances) {
        if (!elementId.includes('_disposables') && !elementId.includes('_resize')) {
            monacoEditor.dispose(elementId);
        }
    }
});

async function initializeBootstrap(maxRetries = 3, baseDelay = 500) {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            // Check if Bootstrap is loaded
            if (typeof bootstrap !== 'undefined') {
                // Initialize tooltips
                const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
                tooltips.forEach(tooltip => new bootstrap.Tooltip(tooltip));
                return true;
            }

            // Wait with exponential backoff
            const delay = baseDelay * Math.pow(2, attempt);
            await new Promise(resolve => setTimeout(resolve, delay));
        } catch (error) {
            console.warn(`Bootstrap initialization attempt ${attempt + 1} failed:`, error);
            if (attempt === maxRetries - 1) {
                throw new Error('Failed to initialize Bootstrap after multiple attempts. Please check your internet connection and refresh the page.');
            }
        }
    }
    return false;
}

// Enhanced error handling and execution
async function executeCode() {
    const runButton = document.getElementById('runButton');
    const output = document.getElementById('output');
    const languageSelect = document.getElementById('languageSelect');

    if (!runButton || !output || !languageSelect || !window.codeEditor) {
        monacoEditor.showNotification('error', 'Éléments requis non trouvés');
        return;
    }

    try {
        runButton.disabled = true;
        runButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Exécution...';
        output.innerHTML = '<div class="alert alert-info">Exécution en cours...</div>';

        const response = await fetch('/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                code: window.codeEditor.getValue(),
                language: languageSelect.value
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();

        if (result.error) {
            output.innerHTML = `<div class="alert alert-danger">
                <strong>Erreur:</strong><br>
                <pre class="mb-0">${result.error}</pre>
            </div>`;
        } else {
            output.innerHTML = result.output ?
                `<pre class="console-output success">${result.output}</pre>` :
                '<div class="alert alert-success">Programme exécuté avec succès sans sortie.</div>';
        }
    } catch (error) {
        output.innerHTML = `<div class="alert alert-danger">
            <strong>Erreur d'exécution:</strong><br>
            <pre class="mb-0">${error.message}</pre>
        </div>`;
    } finally {
        runButton.disabled = false;
        runButton.innerHTML = '<i class="bi bi-play-fill"></i> Exécuter';
    }
}