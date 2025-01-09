// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;
let lastExecution = 0;
let isConsoleReady = false;
const MIN_EXECUTION_INTERVAL = 1000;
const MAX_INIT_RETRIES = 5;
let initRetries = 0;

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

async function executeCode() {
    if (!editor || !isConsoleReady || isExecuting) {
        return;
    }

    isExecuting = true;
    const code = editor.getValue().trim();

    try {
        const languageSelect = document.getElementById('languageSelect');
        const language = languageSelect ? languageSelect.value : 'cpp';
        await consoleInstance.executeCode(code, language);
    } catch (error) {
        console.error('Error executing code:', error);
        const consoleOutput = document.getElementById('consoleOutput');
        if (consoleOutput) {
            consoleOutput.innerHTML = `<div class="console-error">Error: ${error.message}</div>`;
        }
    } finally {
        isExecuting = false;
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

    // Initialize console
    try {
        consoleInstance = new InteractiveConsole();
        await consoleInstance.init();
        isConsoleReady = true;
    } catch (error) {
        console.error('Console initialization failed:', error);
    }

    // Set initial template
    const language = languageSelect ? languageSelect.value : 'cpp';
    editor.setValue(getTemplateForLanguage(language));
    editor.refresh();

    // Run button handler
    if (runButton) {
        runButton.addEventListener('click', async function(e) {
            e.preventDefault();
            if (!isExecuting && isConsoleReady) {
                // Show loading state
                runButton.disabled = true;
                runButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running...';
                
                try {
                    await executeCode();
                } catch (error) {
                    console.error('Error executing code:', error);
                } finally {
                    // Reset button state
                    runButton.disabled = false;
                    runButton.innerHTML = 'Run';
                }
            }
        });
    }

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


    // Clear console handler
    const clearConsoleButton = document.getElementById('clearConsoleButton');
    if (clearConsoleButton) {
        clearConsoleButton.addEventListener('click', async function() {
            if (consoleInstance) {
                await consoleInstance.endSession();
            }
            if (consoleOutput) {
                consoleOutput.innerHTML = '';
            }
        });
    }
});

// Initialize everything when DOM is ready
// Wait for console to be ready
window.addEventListener('consoleReady', () => {
    isConsoleReady = true;
});