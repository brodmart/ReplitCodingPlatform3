// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;
let lastExecution = 0;
let isConsoleReady = false;

function initializeConsole() {
    // Wait for DOM elements to be ready
    const consoleOutput = document.getElementById('consoleOutput');
    const consoleInput = document.getElementById('consoleInput');

    if (!consoleOutput || !consoleInput) {
        console.error('Console elements not ready, retrying in 100ms...');
        setTimeout(initializeConsole, 100);
        return;
    }

    console.log('Initializing editor and console...');
    consoleInstance = new InteractiveConsole();
    isConsoleReady = true;

    // Initialize CodeMirror after console is ready
    initializeEditor();
}

function initializeEditor() {
    // Initialize CodeMirror with basic settings
    const editorElement = document.getElementById('editor');
    if (!editorElement) {
        console.error('Editor element not found');
        return;
    }

    // Initialize CodeMirror with basic settings
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

    // Make editor visible immediately after initialization
    editor.getWrapperElement().classList.add('CodeMirror-initialized');
    console.log('Editor initialized');

    // Set up event listeners
    setupEventListeners();
}

function setupEventListeners() {
    // Get language select and set initial template
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        const initialLanguage = languageSelect.value;
        console.log('Setting initial language:', initialLanguage);
        updateEditorMode(initialLanguage);
        setEditorTemplate(initialLanguage);
    }

    // Run button handler
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', async function(e) {
            e.preventDefault();
            if (!isExecuting) {
                await executeCode();
            }
        });
        console.log('Run button handler attached');
    }

    // Keyboard shortcut
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !isExecuting) {
            e.preventDefault();
            executeCode();
        }
    });
}

// Start initialization when DOM is ready
document.addEventListener('DOMContentLoaded', initializeConsole);

async function executeCode() {
    console.log('Starting code execution...');

    if (!editor || !isConsoleReady || isExecuting) {
        console.error('Execute prevented:', {
            hasEditor: !!editor,
            isConsoleReady,
            isExecuting
        });
        return;
    }

    const runButton = document.getElementById('runButton');

    try {
        isExecuting = true;
        lastExecution = Date.now();

        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running...';
        }

        // Clear previous output and show compiling message
        if (consoleInstance) {
            consoleInstance.clear();
            consoleInstance.disable();
            consoleInstance.appendOutput('Compiling and running code...\n', 'console-info');
        }

        const code = editor.getValue().trim();
        if (!code) {
            throw new Error('No code to execute');
        }

        const languageSelect = document.getElementById('languageSelect');
        const language = languageSelect ? languageSelect.value : 'cpp';
        console.log('Executing code in language:', language);

        // Get CSRF token from meta tag
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            throw new Error('CSRF token not found');
        }

        console.log('Sending code execution request...');
        const response = await fetch('/activities/run_code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            },
            body: JSON.stringify({
                code: code,
                language: language
            })
        });

        console.log('Response status:', response.status);
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Server error response:', errorText);
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        console.log('Execution result:', result);

        if (result.success) {
            if (consoleInstance) {
                consoleInstance.clear();
                consoleInstance.setSuccess('Compilation successful\n');
                if (result.output) {
                    consoleInstance.appendOutput(result.output);
                } else {
                    consoleInstance.appendOutput('Program completed with no output\n');
                }
            }
        } else {
            throw new Error(result.error || 'Failed to execute code');
        }
    } catch (error) {
        console.error('Error executing code:', error);
        if (consoleInstance) {
            consoleInstance.setError(`Error: ${error.message}`);
        }
    } finally {
        isExecuting = false;
        if (runButton) {
            runButton.disabled = false;
            runButton.innerHTML = 'Run';
        }
        if (consoleInstance) {
            consoleInstance.enable();
        }
    }
}

function updateEditorMode(language) {
    if (!editor) {
        console.error('Editor not initialized');
        return;
    }

    console.log('Updating editor mode for:', language);
    if (language === 'cpp') {
        editor.setOption('mode', 'text/x-c++src');
    } else if (language === 'csharp') {
        editor.setOption('mode', 'text/x-csharp');
    }
}

function setEditorTemplate(language) {
    if (!editor) {
        console.error('Editor not initialized');
        return;
    }

    const template = getTemplateForLanguage(language);
    console.log('Setting template for', language);
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
    return ''; // Default empty template
}

// Helper function to escape HTML for safe display
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}