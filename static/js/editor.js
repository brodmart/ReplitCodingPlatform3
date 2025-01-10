// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;
let lastExecution = 0;
let isConsoleReady = false;
const MIN_EXECUTION_INTERVAL = 1000;
const INITIAL_POLL_INTERVAL = 100;
const MAX_POLL_INTERVAL = 2000;
const BACKOFF_FACTOR = 1.5;

async function executeCode() {
    console.log('executeCode called');
    if (!editor || !isConsoleReady || isExecuting) {
        console.error('Execute prevented:', {
            hasEditor: !!editor,
            isConsoleReady,
            isExecuting
        });
        return;
    }

    const runButton = document.getElementById('runButton');
    const consoleOutput = document.getElementById('consoleOutput');

    try {
        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running...';
        }

        isExecuting = true;
        const code = editor.getValue().trim();
        const languageSelect = document.getElementById('languageSelect');
        const language = languageSelect ? languageSelect.value : 'cpp';

        console.log('Starting execution with:', { language, codeLength: code.length });

        if (!consoleInstance) {
            throw new Error('Console instance not available');
        }

        if (!consoleInstance.isInitialized) {
            throw new Error('Console is not fully initialized');
        }

        // Clear any existing input state before execution
        sessionStorage.removeItem('console_input_state');

        const result = await consoleInstance.executeCode(code, language);
        console.log('Execution result:', result);

        if (!result) {
            throw new Error('Failed to execute code');
        }
    } catch (error) {
        console.error('Error executing code:', error);
        if (consoleOutput) {
            consoleOutput.innerHTML = `<div class="console-error">Error: ${error.message}</div>`;
        }
    } finally {
        isExecuting = false;
        if (runButton) {
            runButton.disabled = false;
            runButton.innerHTML = 'Run';
        }
    }
}

function getTemplateForLanguage(language) {
    if (language === 'cpp') {
        return `#include <iostream>
#include <string>
using namespace std;

int main() {
    string name;
    cout << "Enter your name: ";
    getline(cin, name);
    cout << "Hello, " << name << "!" << endl;
    return 0;
}`;
    } else {
        return `using System;

namespace ProgrammingActivity
{
    class Program 
    {
        static void Main(string[] args)
        {
            Console.Write("Enter your name: ");
            string name = Console.ReadLine();
            Console.WriteLine($"Hello, {name}!");
        }
    }
}`;
    }
}

document.addEventListener('DOMContentLoaded', async function() {
    console.log('DOM Content Loaded');
    const editorElement = document.getElementById('editor');
    const languageSelect = document.getElementById('languageSelect');
    const consoleOutput = document.getElementById('consoleOutput');
    const runButton = document.getElementById('runButton');

    if (!editorElement || !consoleOutput) {
        console.error('Required elements not found');
        return;
    }

    // Initialize CodeMirror
    editor = CodeMirror.fromTextArea(editorElement, {
        mode: 'text/x-c++src',
        theme: 'dracula',
        lineNumbers: true,
        autoCloseBrackets: true,
        matchBrackets: true,
        indentUnit: 4,
        tabSize: 4,
        lineWrapping: true
    });

    // Initialize console with proper error handling
    try {
        console.log('Initializing console...');
        if (consoleInstance) {
            await consoleInstance.endSession();
            consoleInstance = null;
        }

        consoleInstance = new InteractiveConsole();
        const initSuccess = await consoleInstance.init();

        if (!initSuccess) {
            throw new Error('Console initialization failed');
        }

        isConsoleReady = true;
        console.log('Console initialization complete');
    } catch (error) {
        console.error('Console initialization failed:', error);
        if (consoleOutput) {
            consoleOutput.innerHTML = `<div class="console-error">Failed to initialize console: ${error.message}</div>`;
        }
        if (runButton) {
            runButton.disabled = true;
        }
        return;
    }

    // Set initial template
    const language = languageSelect ? languageSelect.value : 'cpp';
    editor.setValue(getTemplateForLanguage(language));
    editor.refresh();

    // Language change handler
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const language = this.value;
            editor.setOption('mode', language === 'cpp' ? 'text/x-c++src' : 'text/x-csharp');
            // Only set template if editor is empty
            if (editor.getValue().trim() === '') {
                editor.setValue(getTemplateForLanguage(language));
            }
            editor.refresh();
        });
    }

    // Keyboard shortcut
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !isExecuting) {
            e.preventDefault();
            executeCode();
        }
    });

    // Run button handler
    if (runButton) {
        runButton.addEventListener('click', async function(e) {
            e.preventDefault();
            if (!isExecuting && isConsoleReady) {
                await executeCode();
            }
        });
    }
});

// Wait for console to be ready
window.addEventListener('consoleReady', () => {
    isConsoleReady = true;
});