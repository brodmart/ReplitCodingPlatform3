// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;

document.addEventListener('DOMContentLoaded', function() {
    initializeComponents();
});

function initializeComponents() {
    try {
        // Initialize editor first
        const editorElement = document.getElementById('editor');
        if (!editorElement) {
            throw new Error('Editor element not found');
        }

        // Enhanced CodeMirror initialization with better language support
        editor = CodeMirror.fromTextArea(editorElement, {
            mode: 'text/x-c++src', // Default to C++
            theme: 'dracula',
            lineNumbers: true,
            autoCloseBrackets: true,
            matchBrackets: true,
            indentUnit: 4,
            tabSize: 4,
            lineWrapping: true,
            viewportMargin: Infinity,
            gutters: ["CodeMirror-linenumbers", "CodeMirror-lint-markers"],
            extraKeys: {
                "Tab": function(cm) {
                    if (cm.somethingSelected()) {
                        cm.indentSelection("add");
                    } else {
                        cm.replaceSelection("    ", "end");
                    }
                },
                "Ctrl-Enter": executeCode,
                "Cmd-Enter": executeCode,
                "Ctrl-/": "toggleComment",
                "Cmd-/": "toggleComment"
            },
            autoCloseTags: true,
            foldGutter: true,
            matchTags: {bothTags: true}
        });

        editor.on('change', function() {
            // Auto-save content
            localStorage.setItem('editorContent', editor.getValue());
        });

        editor.getWrapperElement().classList.add('CodeMirror-initialized');

        // Initialize console after editor is ready
        initializeConsole();

    } catch (error) {
        console.error('Failed to initialize components:', error);
        showError('Failed to initialize editor. Please refresh the page.');
    }
}

function initializeConsole() {
    try {
        // Check if Console class is loaded
        if (typeof InteractiveConsole === 'undefined') {
            throw new Error('Console class not loaded');
        }

        // Wait for console elements before initializing
        waitForConsoleElements()
            .then(() => {
                consoleInstance = new InteractiveConsole();
                setupEventListeners();
                setInitialEditorState();

                // Restore previous content if any
                const savedContent = localStorage.getItem('editorContent');
                if (savedContent) {
                    editor.setValue(savedContent);
                }
            })
            .catch(error => {
                console.error('Failed to initialize console:', error);
                showError('Failed to initialize console. Please refresh the page.');
            });
    } catch (error) {
        console.error('Error in console initialization:', error);
        showError('Failed to initialize console. Please refresh the page.');
    }
}

function showError(message) {
    const errorMessage = document.createElement('div');
    errorMessage.className = 'alert alert-danger';
    errorMessage.textContent = message;
    document.body.insertBefore(errorMessage, document.body.firstChild);
}

function waitForConsoleElements(retries = 10) {
    return new Promise((resolve, reject) => {
        const check = (attempts) => {
            const consoleOutput = document.getElementById('consoleOutput');
            const consoleInput = document.getElementById('consoleInput');

            if (consoleOutput && consoleInput) {
                resolve();
            } else if (attempts <= 0) {
                reject(new Error('Console elements not found after maximum retries'));
            } else {
                setTimeout(() => check(attempts - 1), 100);
            }
        };
        check(retries);
    });
}

function setupEventListeners() {
    // Run button handler
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', function(e) {
            e.preventDefault();
            if (!isExecuting) {
                executeCode();
            }
        });
    }

    // Language select handler with improved mode switching
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const language = this.value;
            updateEditorMode(language);
            setEditorTemplate(language);

            // Store selected language
            localStorage.setItem('selectedLanguage', language);
        });
    }

    // Add keyboard shortcuts listener
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + S to prevent default save
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            // Auto-save is already happening on change
        }
    });
}

function setInitialEditorState() {
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        // Restore previously selected language or default to cpp
        const savedLanguage = localStorage.getItem('selectedLanguage') || 'cpp';
        languageSelect.value = savedLanguage;
        updateEditorMode(savedLanguage);
        setEditorTemplate(savedLanguage);
    }
}

async function executeCode() {
    if (!editor || !consoleInstance) {
        console.error('Editor or console not initialized');
        return;
    }

    if (isExecuting) {
        return;
    }

    const runButton = document.getElementById('runButton');
    isExecuting = true;

    try {
        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...';
        }

        consoleInstance.clear();
        consoleInstance.disable();
        consoleInstance.appendOutput('Compiling and running code...\n');

        const code = editor.getValue().trim();
        if (!code) {
            throw new Error('No code to execute');
        }

        const languageSelect = document.getElementById('languageSelect');
        const language = languageSelect ? languageSelect.value : 'cpp';

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            throw new Error('CSRF token not found');
        }

        const response = await fetch('/activities/run_code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            },
            body: JSON.stringify({ code, language })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();

        if (result.success) {
            consoleInstance.clear();
            consoleInstance.appendOutput('Compilation successful!\n', 'success');
            if (result.output) {
                consoleInstance.appendOutput(result.output);
            }

            // Highlight any warnings
            if (result.warnings) {
                result.warnings.forEach(warning => {
                    const line = warning.line - 1;
                    editor.addLineClass(line, 'background', 'line-warning');
                });
            }
        } else {
            handleCompilationError(result.error);
        }
    } catch (error) {
        console.error('Error executing code:', error);
        handleExecutionError(error.message);
    } finally {
        isExecuting = false;
        if (runButton) {
            runButton.disabled = false;
            runButton.innerHTML = 'Run';
        }
        consoleInstance.enable();
    }
}

function handleCompilationError(error) {
    // Clear previous error markers
    editor.clearGutter("CodeMirror-lint-markers");

    // Parse error message to extract line number if available
    const errorMatch = error.match(/line (\d+)/i);
    if (errorMatch) {
        const lineNum = parseInt(errorMatch[1]) - 1;
        const marker = document.createElement('div');
        marker.className = 'CodeMirror-lint-marker CodeMirror-lint-marker-error';
        marker.title = error;
        editor.setGutterMarker(lineNum, "CodeMirror-lint-markers", marker);
        editor.addLineClass(lineNum, 'background', 'line-error');
    }

    consoleInstance.setError(error);
}

function handleExecutionError(error) {
    consoleInstance.setError(`Runtime Error: ${error}`);
}

function updateEditorMode(language) {
    if (!editor) return;

    const modes = {
        'cpp': 'text/x-c++src',
        'csharp': 'text/x-csharp'
    };

    editor.setOption('mode', modes[language] || modes.cpp);

    // Update lint options based on language
    editor.setOption('lint', {
        'cpp': {
            esversion: 6,
            asi: true
        },
        'csharp': {
            esversion: 6,
            asi: true
        }
    }[language] || {});
}

function setEditorTemplate(language) {
    if (!editor) return;
    const template = getTemplateForLanguage(language);
    editor.setValue(template);
    editor.setCursor(editor.lineCount() - 2, 0); // Position cursor at second to last line
}

function getTemplateForLanguage(language) {
    if (language === 'cpp') {
        return `#include <iostream>
using namespace std;

int main() {
    cout << "Hello World!" << endl;
    return 0;
}`;
    } else if (language === 'csharp') {
        return `using System;

class Program 
{
    static void Main(string[] args)
    {
        Console.WriteLine("Hello World!");
    }
}`;
    }
    return '';
}