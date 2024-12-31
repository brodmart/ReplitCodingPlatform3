let editor;
const monacoEditor = {
    // Keep track of initialization state and instances
    initialized: false,
    instances: new Map(),

    initialize: function(elementId, options = {}) {
        return new Promise((resolve, reject) => {
            // Check if element exists before proceeding
            const editorElement = document.getElementById(elementId);
            if (!editorElement) {
                reject(new Error(`Editor element with id '${elementId}' not found`));
                return;
            }

            // Cleanup existing instance if present
            this.dispose(elementId);

            // Configure require.js only once
            if (!window.requirejs) {
                require.config({
                    paths: {
                        'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs'
                    }
                });
            }

            try {
                require(['vs/editor/editor.main'], () => {
                    // Enhanced default options with better performance settings
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
                        // Performance optimizations
                        fastScrollSensitivity: 5,
                        scrollbar: {
                            useShadows: false,
                            verticalScrollbarSize: 10,
                            horizontalScrollbarSize: 10
                        },
                        // Better error handling
                        onDidAttemptReadOnlyEdit: () => {
                            this.showNotification('warning', 'Ce fichier est en lecture seule');
                        }
                    };

                    // Create new editor instance
                    const editorInstance = monaco.editor.create(editorElement, {
                        ...defaultOptions,
                        ...options
                    });

                    // Store instance and attach cleanup handlers
                    this.instances.set(elementId, editorInstance);
                    this.setupEditorEventHandlers(editorInstance, elementId);

                    // Set global reference and mark as initialized
                    editor = editorInstance;
                    this.initialized = true;

                    resolve(editorInstance);
                });
            } catch (error) {
                console.error('Editor initialization error:', error);
                this.showNotification('error', 'Erreur lors de l\'initialisation de l\'éditeur');
                reject(error);
            }
        });
    },

    setupEditorEventHandlers: function(editorInstance, elementId) {
        // Debounced content change handler
        let changeTimeout;
        const contentChangeHandler = () => {
            if (changeTimeout) clearTimeout(changeTimeout);
            changeTimeout = setTimeout(() => {
                this.onContentChanged(editorInstance);
            }, 300);
        };

        // Attach handlers
        const disposables = [];
        disposables.push(
            editorInstance.onDidChangeModelContent(contentChangeHandler),
            editorInstance.onDidBlurEditorText(() => {
                this.saveEditorState(elementId, editorInstance.getValue());
            })
        );

        // Store disposables for cleanup
        this.instances.set(elementId + '_disposables', disposables);

        // Window resize handler with debounce
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
        // Cleanup previous instance if exists
        const existingInstance = this.instances.get(elementId);
        if (existingInstance) {
            // Dispose event handlers
            const disposables = this.instances.get(elementId + '_disposables') || [];
            disposables.forEach(d => d.dispose());

            // Remove resize listener
            const resizeHandler = this.instances.get(elementId + '_resize');
            if (resizeHandler) {
                window.removeEventListener('resize', resizeHandler);
            }

            // Dispose editor
            existingInstance.dispose();

            // Clear from instances map
            this.instances.delete(elementId);
            this.instances.delete(elementId + '_disposables');
            this.instances.delete(elementId + '_resize');
        }
    },

    onContentChanged: function(editorInstance) {
        // Implement auto-save or validation logic here
        const value = editorInstance.getValue();
        // You could trigger validation or auto-save here
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

// Bootstrap initialization with retry
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

// Initialize event handlers when document is ready
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // First, ensure Bootstrap is initialized
        await initializeBootstrap();

        const editorElement = document.getElementById('editor');
        if (!editorElement) {
            console.warn('Editor element not found, might be on a different page');
            return;
        }

        // Initialize Monaco editor
        const editor = await monacoEditor.initialize('editor', {
            value: editorElement.getAttribute('data-initial-value') || '',
            language: editorElement.getAttribute('data-language') || 'cpp',
            readOnly: false,
            wordWrap: 'on',
            minimap: { enabled: true }
        });

        // Set up event handlers only if editor is initialized
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
    // Cleanup all editor instances
    for (const [elementId] of monacoEditor.instances) {
        if (!elementId.includes('_disposables') && !elementId.includes('_resize')) {
            monacoEditor.dispose(elementId);
        }
    }
});