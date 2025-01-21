// Initialize variables
let editor = null;
let consoleInstance = null;
let isExecuting = false;

document.addEventListener('DOMContentLoaded', async function() {
    try {
        await initializeEditor();
        console.log('Editor initialized successfully');
    } catch (error) {
        console.error('Failed to initialize editor:', error);
        showError('Failed to initialize editor. Please refresh the page.');
    }
});

async function initializeEditor() {
    // Initialize CodeMirror
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

    // Initialize console
    await initializeConsole();

    // Set up event listeners
    setupEventListeners();

    // Set initial content
    const savedContent = localStorage.getItem('editorContent');
    if (savedContent) {
        editor.setValue(savedContent);
    } else {
        setEditorTemplate('cpp');
    }

    editor.refresh();
}

async function initializeConsole() {
    const outputElement = document.getElementById('consoleOutput');
    const inputElement = document.getElementById('consoleInput');

    if (!outputElement || !inputElement) {
        throw new Error('Console elements not found');
    }

    consoleInstance = new InteractiveConsole({
        outputElement: outputElement,
        inputElement: inputElement,
        onCommand: handleConsoleCommand,
        onInput: handleConsoleInput
    });
}

function setupEventListeners() {
    // Run button handler
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', executeCode);
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

    // Clear console button
    const clearButton = document.getElementById('clearConsole');
    if (clearButton) {
        clearButton.addEventListener('click', () => {
            consoleInstance?.clear();
        });
    }

    // Auto-save editor content
    editor.on('change', function() {
        localStorage.setItem('editorContent', editor.getValue());
    });
}

async function executeCode() {
    if (!editor || !consoleInstance || isExecuting) return;

    isExecuting = true;
    const runButton = document.getElementById('runButton');

    try {
        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...';
        }

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

        consoleInstance.clear();
        consoleInstance.appendOutput('Compiling and running code...\n');

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
            consoleInstance.appendSuccess('Compilation successful!\n');
            if (result.output) {
                consoleInstance.appendOutput(result.output);
            }
        } else {
            consoleInstance.appendError(result.error);
        }
    } catch (error) {
        console.error('Error executing code:', error);
        consoleInstance.appendError(`Error: ${error.message}`);
    } finally {
        isExecuting = false;
        if (runButton) {
            runButton.disabled = false;
            runButton.innerHTML = 'Run';
        }
    }
}

function updateEditorMode(language) {
    const modes = {
        'cpp': 'text/x-c++src',
        'csharp': 'text/x-csharp'
    };
    editor.setOption('mode', modes[language] || modes.cpp);
}

function setEditorTemplate(language) {
    const templates = {
        'cpp': `#include <iostream>
using namespace std;

int main() {
    // Your C++ code here
    cout << "Hello World!" << endl;
    return 0;
}`,
        'csharp': `using System;

class Program 
{
    static void Main(string[] args)
    {
        // Your C# code here
        Console.WriteLine("Hello World!");
    }
}`
    };

    if (editor) {
        const template = templates[language] || templates.cpp;
        editor.setValue(template);
        editor.setCursor(editor.lineCount() - 2, 0);
    }
}

async function handleConsoleCommand(command) {
    if (!editor || !consoleInstance) return;

    try {
        const response = await executeCommand(command);
        consoleInstance.appendOutput(response);
    } catch (error) {
        consoleInstance.appendOutput(`Error: ${error.message}`, 'error');
    }
}

async function handleConsoleInput(input) {
    if (activeProcess) {
        activeProcess.sendInput(input);
    }
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger';
    errorDiv.textContent = message;
    document.body.insertBefore(errorDiv, document.body.firstChild);
    setTimeout(() => errorDiv.remove(), 5000);
}

async function executeCommand(command) {
    const languageSelect = document.getElementById('languageSelect');
    const language = languageSelect ? languageSelect.value : 'cpp';

    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            throw new Error('CSRF token not found');
        }

        const response = await fetch('/execute_command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            },
            body: JSON.stringify({ command, language })
        });

        if (!response.ok) {
            throw new Error('Failed to execute command');
        }

        return response.text();
    } catch (error) {
        console.error('Execute command error:', error);
        throw error;
    }
}

waitForConsoleElements = function waitForConsoleElements(maxRetries = 10, interval = 100) {
    return new Promise((resolve, reject) => {
        let attempts = 0;

        const checkElements = () => {
            const output = document.getElementById('consoleOutput');
            const input = document.getElementById('consoleInput');

            if (output && input) {
                resolve({ output, input });
            } else if (attempts >= maxRetries) {
                reject(new Error('Console elements not found after maximum retries'));
            } else {
                attempts++;
                setTimeout(checkElements, interval);
            }
        };

        checkElements();
    });
};