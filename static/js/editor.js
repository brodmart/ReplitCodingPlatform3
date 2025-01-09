// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;
let lastExecution = 0;
let isConsoleReady = false;
const MIN_EXECUTION_INTERVAL = 1000;

async function executeCode() {
    if (!editor || !isConsoleReady || isExecuting) {
        console.log('Execute prevented:', {
            hasEditor: !!editor,
            isConsoleReady,
            isExecuting
        });
        return;
    }

    const runButton = document.getElementById('runButton');
    try {
        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running...';
        }

        isExecuting = true;
        const code = editor.getValue().trim();
        const languageSelect = document.getElementById('languageSelect');
        const language = languageSelect ? languageSelect.value : 'cpp';

        console.log('Preparing to execute:', { language, codeLength: code.length });

        if (!consoleInstance) {
            throw new Error('Console instance not initialized');
        }

        await consoleInstance.executeCode(code, language);
    } catch (error) {
        console.error('Error executing code:', error);
        const consoleOutput = document.getElementById('consoleOutput');
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

    // Initialize console with delay to ensure DOM is ready
    setTimeout(async () => {
        try {
            consoleInstance = new InteractiveConsole();
            await consoleInstance.init();
            isConsoleReady = true;
            console.log('Console initialized successfully');
        } catch (error) {
            console.error('Console initialization failed:', error);
            if (consoleOutput) {
                consoleOutput.innerHTML = `<div class="console-error">Failed to initialize console: ${error.message}</div>`;
            }
        }
    }, 500);

    // Set initial template
    const language = languageSelect ? languageSelect.value : 'cpp';
    editor.setValue(getTemplateForLanguage(language));
    editor.refresh();

    // Language change handler
    if (languageSelect) {
        languageSelect.addEventListener('change', () => {
            const language = languageSelect.value;
            editor.setOption('mode', language === 'cpp' ? 'text/x-c++src' : 'text/x-csharp');
            editor.setValue(getTemplateForLanguage(language));
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