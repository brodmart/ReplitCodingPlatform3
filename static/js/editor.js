// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize CodeMirror first
    initializeEditor();

    // Then initialize console
    initializeConsole();

    // Set up event listeners
    setupEventListeners();
});

function initializeEditor() {
    const editorElement = document.getElementById('editor');
    if (!editorElement) {
        console.error('Editor element not found');
        return;
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
            "Ctrl-Enter": function() {
                if (!isExecuting) {
                    executeCode();
                }
            }
        }
    });

    // Make editor visible
    editor.getWrapperElement().classList.add('CodeMirror-initialized');
}

function initializeConsole() {
    if (typeof InteractiveConsole === 'undefined') {
        console.error('InteractiveConsole class not loaded');
        return;
    }

    consoleInstance = new InteractiveConsole();
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
        const initialLanguage = languageSelect.value || 'cpp';
        updateEditorMode(initialLanguage);
        setEditorTemplate(initialLanguage);

        languageSelect.addEventListener('change', function() {
            const language = this.value;
            updateEditorMode(language);
            setEditorTemplate(language);
        });
    }
}

async function executeCode() {
    if (!editor || !consoleInstance) {
        console.error('Editor or console not initialized');
        return;
    }

    if (isExecuting) {
        console.log('Code execution already in progress');
        return;
    }

    const runButton = document.getElementById('runButton');
    isExecuting = true;

    try {
        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...';
        }

        // Clear previous output
        consoleInstance.clear();
        consoleInstance.appendOutput('Compiling and running code...\n');

        const code = editor.getValue().trim();
        if (!code) {
            throw new Error('No code to execute');
        }

        const languageSelect = document.getElementById('languageSelect');
        const language = languageSelect ? languageSelect.value : 'cpp';

        // Get CSRF token
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
    editor.setCursor(0, 0);
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

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}