// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;
let lastExecution = 0;
const MIN_EXECUTION_INTERVAL = 1000;
const MAX_INIT_RETRIES = 3;
let initRetries = 0;

// Function definitions outside DOMContentLoaded
function setExecutionState(executing) {
    isExecuting = executing;
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.disabled = executing;
        runButton.innerHTML = executing ? 
            `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running...` :
            (document.documentElement.lang === 'fr' ? 'Exécuter' : 'Run');
    }
}

async function waitForConsoleReady(maxWait = 5000) {
    const startTime = Date.now();
    while (Date.now() - startTime < maxWait) {
        if (consoleInstance && !consoleInstance.isBusy && consoleInstance.isInitialized) {
            return true;
        }
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    return false;
}

async function ensureConsoleInitialized() {
    if (!consoleInstance || !consoleInstance.isInitialized) {
        if (initRetries >= MAX_INIT_RETRIES) {
            throw new Error("Failed to initialize console after multiple attempts");
        }
        initRetries++;

        try {
            consoleInstance = new InteractiveConsole({
                lang: document.documentElement.lang || 'en'
            });

            const isReady = await waitForConsoleReady();
            if (!isReady) {
                throw new Error("Console initialization timed out");
            }

            return consoleInstance;
        } catch (error) {
            console.error("Console initialization error:", error);
            throw error;
        }
    }
    return consoleInstance;
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

// Global executeCode function
window.executeCode = async function() {
    if (!editor) {
        console.error('Editor not initialized');
        return;
    }

    if (isExecuting || Date.now() - lastExecution < MIN_EXECUTION_INTERVAL) {
        return;
    }

    const code = editor.getValue().trim();
    if (!code) {
        const consoleOutput = document.getElementById('consoleOutput');
        if (consoleOutput) {
            consoleOutput.innerHTML = '<div class="console-error">Error: No code to execute</div>';
        }
        return;
    }

    try {
        setExecutionState(true);
        lastExecution = Date.now();

        // Initialize console if needed
        const console = await ensureConsoleInitialized();
        if (!console) {
            throw new Error("Failed to initialize console");
        }

        const languageSelect = document.getElementById('languageSelect');
        const language = languageSelect ? languageSelect.value : 'cpp';
        await console.executeCode(code, language);

    } catch (error) {
        console.error('Error executing code:', error);
        const consoleOutput = document.getElementById('consoleOutput');
        if (consoleOutput) {
            consoleOutput.innerHTML = `<div class="console-error">Error: ${error.message}</div>`;
        }
    } finally {
        setExecutionState(false);
    }
};

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', async function() {
    const editorElement = document.getElementById('editor');
    const languageSelect = document.getElementById('languageSelect');
    const clearConsoleButton = document.getElementById('clearConsoleButton');
    const consoleOutput = document.getElementById('consoleOutput');

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
        lineWrapping: true,
        gutters: ["CodeMirror-linenumbers"],
        extraKeys: {
            "Ctrl-Space": "autocomplete",
            "F11": function(cm) {
                cm.setOption("fullScreen", !cm.getOption("fullScreen"));
            },
            "Esc": function(cm) {
                if (cm.getOption("fullScreen")) cm.setOption("fullScreen", false);
            }
        }
    });

    // Set initial template
    const initialLanguage = languageSelect ? languageSelect.value : 'cpp';
    editor.setValue(editor.getValue() || getTemplateForLanguage(initialLanguage));
    editor.refresh();

    // Language change handler
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const language = this.value;
            editor.setOption('mode', language === 'cpp' ? 'text/x-c++src' : 'text/x-csharp');
            if (!editor.getValue().trim()) {
                editor.setValue(getTemplateForLanguage(language));
                editor.refresh();
            }
        });
    }

    // Run button handler
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', function(e) {
            e.preventDefault();
            window.executeCode();
        });
    }

    // Keyboard shortcut
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !isExecuting) {
            e.preventDefault();
            window.executeCode();
        }
    });

    // Clear console handler
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

    // Initialize console
    try {
        await ensureConsoleInitialized();
    } catch (error) {
        console.error('Initial console initialization failed:', error);
    }
});