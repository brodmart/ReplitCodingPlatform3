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

        editor = CodeMirror.fromTextArea(editorElement, {
            mode: 'text/x-c++src',
            theme: 'dracula',
            lineNumbers: true,
            autoCloseBrackets: true,
            matchBrackets: true,
            indentUnit: 4,
            tabSize: 4,
            lineWrapping: true,
            viewportMargin: Infinity,
            extraKeys: {
                "Tab": function(cm) {
                    if (cm.somethingSelected()) {
                        cm.indentSelection("add");
                    } else {
                        cm.replaceSelection("    ", "end");
                    }
                },
                "Ctrl-Enter": executeCode,
                "Cmd-Enter": executeCode
            }
        });

        editor.getWrapperElement().classList.add('CodeMirror-initialized');

        // Wait for console elements before initializing console
        waitForConsoleElements()
            .then(() => {
                // Initialize console after editor
                if (typeof InteractiveConsole === 'undefined') {
                    throw new Error('InteractiveConsole class not loaded');
                }
                consoleInstance = new InteractiveConsole();

                // Set up event listeners after both components are initialized
                setupEventListeners();
                setInitialEditorState();
            })
            .catch(error => {
                console.error('Failed to initialize console:', error);
                const errorMessage = document.createElement('div');
                errorMessage.className = 'alert alert-danger';
                errorMessage.textContent = 'Failed to initialize console. Please refresh the page.';
                document.body.insertBefore(errorMessage, document.body.firstChild);
            });

    } catch (error) {
        console.error('Failed to initialize components:', error);
        const errorMessage = document.createElement('div');
        errorMessage.className = 'alert alert-danger';
        errorMessage.textContent = 'Failed to initialize editor. Please refresh the page.';
        document.body.insertBefore(errorMessage, document.body.firstChild);
    }
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
                console.log('Console elements not ready, retrying in 100ms...');
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

    // Language select handler
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const language = this.value;
            updateEditorMode(language);
            setEditorTemplate(language);
        });
    }
}

function setInitialEditorState() {
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        const initialLanguage = languageSelect.value || 'cpp';
        updateEditorMode(initialLanguage);
        setEditorTemplate(initialLanguage);
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
        } else {
            throw new Error(result.error || 'Failed to execute code');
        }
    } catch (error) {
        console.error('Error executing code:', error);
        consoleInstance.setError(error.message);
    } finally {
        isExecuting = false;
        if (runButton) {
            runButton.disabled = false;
            runButton.innerHTML = 'Run';
        }
        consoleInstance.enable();
    }
}

function updateEditorMode(language) {
    if (!editor) return;
    editor.setOption('mode', language === 'cpp' ? 'text/x-c++src' : 'text/x-csharp');
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