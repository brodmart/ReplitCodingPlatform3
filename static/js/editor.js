// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;
let lastExecution = 0;
const MIN_EXECUTION_INTERVAL = 1000;
const MAX_INIT_RETRIES = 5;
let initRetries = 0;
const INIT_DELAY = 500;

async function ensureElementsExist() {
    const elements = ['editor', 'consoleOutput', 'consoleInput'];
    return elements.every(id => document.getElementById(id));
}

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
        if (consoleInstance && consoleInstance.isInitialized && !consoleInstance.isBusy) {
            return true;
        }
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    return false;
}

async function ensureConsoleInitialized() {
    if (!consoleInstance || !consoleInstance.isInitialized) {
        if (initRetries >= MAX_INIT_RETRIES) {
            console.error("Max retries reached, resetting state");
            initRetries = 0;
            consoleInstance = null;
        }

        // Wait for elements to exist
        const elementsExist = await ensureElementsExist();
        if (!elementsExist) {
            await new Promise(resolve => setTimeout(resolve, INIT_DELAY));
            return ensureConsoleInitialized();
        }

        initRetries++;;

        try {
            consoleInstance = new InteractiveConsole({
                lang: document.documentElement.lang || 'en'
            });
            await consoleInstance.init();
            //Added check for successful initialization
            if (!consoleInstance.isInitialized) {
                throw new Error("Console initialization failed despite successful init call.");
            }
            return consoleInstance;
        } catch (error) {
            console.error("Console initialization error:", error);
            //Added retry logic with exponential backoff
            await new Promise(resolve => setTimeout(resolve, initRetries * 1000));
            return ensureConsoleInitialized(); //Retry
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
    try {
        if (!editor) {
            throw new Error('Editor not initialized');
        }

        if (isExecuting) {
            throw new Error('Execution already in progress');
            return;
        }

        // Ensure console is initialized before proceeding
        if (!consoleInstance || !consoleInstance.isInitialized) {
            await ensureConsoleInitialized();
            if (!consoleInstance || !consoleInstance.isInitialized) {
                throw new Error('Failed to initialize console');
            }
        }

    if (Date.now() - lastExecution < MIN_EXECUTION_INTERVAL) {
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
        if (!consoleInstance || !consoleInstance.isInitialized) {
            console.log('Console not ready, reinitializing...');
            await ensureConsoleInitialized();
        }
        
        setExecutionState(true);
        lastExecution = Date.now();
        console.log('Starting execution with state:', {
            consoleReady: consoleInstance?.isInitialized,
            executing: isExecuting
        });

        // Ensure console is initialized and ready
        const console = await ensureConsoleInitialized();
        if (!console) {
            throw new Error("Failed to initialize console");
        }

        // Wait for console to be fully ready
        const isReady = await waitForConsoleReady();
        if (!isReady) {
            throw new Error("Console not ready for execution");
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
    let initAttempts = 0;
    const maxAttempts = 5;
    const initInterval = setInterval(async () => {
        const editorElement = document.getElementById('editor');
        const languageSelect = document.getElementById('languageSelect');
        const consoleOutput = document.getElementById('consoleOutput');

        if (editorElement && consoleOutput && (!editor || !consoleInstance)) {
            clearInterval(initInterval);
            await initializeElements(editorElement, languageSelect, consoleOutput);
        } else if (initAttempts >= maxAttempts) {
            clearInterval(initInterval);
            console.error('Failed to initialize editor after maximum attempts');
        }
        initAttempts++;
    }, 200);

    async function initializeElements(editorElement, languageSelect, consoleOutput) {
    // Wait for all elements to be fully loaded
    await new Promise(resolve => setTimeout(resolve, 100));


    if (!editorElement || !consoleOutput) {
        console.error('Required elements not found');
        return;
    }

    // Force redraw
    editorElement.style.display = 'none';
    editorElement.offsetHeight; // Force reflow
    editorElement.style.display = 'block';

    // Initialize CodeMirror
    editor = CodeMirror.fromTextArea(editorElement, {
        mode: 'text/x-c++src',
        theme: 'dracula',
        onLoad: function() {
            editorElement.classList.add('CodeMirror-initialized');
        },
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

    // Initialize console first
    try {
        await ensureConsoleInitialized();
        console.log('Console initialization complete');
    } catch (error) {
        console.error('Initial console initialization failed:', error);
    }

    // Set up event listeners after console is initialized
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

    // Initialize with empty content first
    editor.setValue('');

    // Language change handler with forced template update
    if (languageSelect) {
        const updateTemplate = () => {
            const language = languageSelect.value;
            editor.setOption('mode', language === 'cpp' ? 'text/x-c++src' : 'text/x-csharp');
            editor.setValue(getTemplateForLanguage(language));
            editor.refresh();
            editor.focus();
        };

        // Set initial template
        updateTemplate();

        // Handle language changes
        languageSelect.addEventListener('change', updateTemplate);
    }

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

    function highlightSyntax() {
        // Add your syntax highlighting logic here if needed.
    }
    highlightSyntax();
    }
});