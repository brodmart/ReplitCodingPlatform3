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

        // Make a POST request to execute the code
        const response = await fetch('/activities/run_code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
            },
            body: JSON.stringify({
                code: code,
                language: language,
                activity_id: document.querySelector('input[name="activity_id"]')?.value || '',
                csrf_token: document.querySelector('meta[name="csrf-token"]').content
            })
        });

        // Check if response is JSON
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            throw new Error('Server returned an invalid response. Please try again.');
        }

        const result = await response.json();
        console.log('Execution result:', result);

        if (result.success) {
            if (consoleOutput) {
                // Handle both string and object outputs
                let outputText = typeof result.output === 'string' ? result.output : JSON.stringify(result.output, null, 2);
                outputText = outputText || 'Program executed successfully with no output.';
                consoleOutput.innerHTML = `<pre class="console-output">${escapeHtml(outputText)}</pre>`;
            }
        } else {
            // Specific error handling
            if (result.error === 'Missing required fields') {
                throw new Error('Please ensure all required fields are provided.');
            } else {
                throw new Error(result.error || 'Failed to execute code');
            }
        }
    } catch (error) {
        console.error('Error executing code:', error);
        if (consoleOutput) {
            consoleOutput.innerHTML = `<div class="console-error">Error: ${escapeHtml(error.message)}</div>`;
        }
    } finally {
        isExecuting = false;
        if (runButton) {
            runButton.disabled = false;
            runButton.innerHTML = '<i class="bi bi-play-fill"></i> Run';
        }
    }
}

// Helper function to escape HTML and prevent XSS
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function getTemplateForLanguage(language) {
    if (language === 'cpp') {
        return `#include <iostream>
using namespace std;

int main() {
    cout << "Hello World!" << endl;
    return 0;
}`;
    } else {
        return `using System;

class Program 
{
    static void Main(string[] args)
    {
        Console.WriteLine("Hello World!");
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

    // Only set template if editor is empty
    const currentCode = editor.getValue().trim();
    if (!currentCode) {
        const language = languageSelect ? languageSelect.value : 'cpp';
        editor.setValue(getTemplateForLanguage(language));
        editor.refresh();
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

    // Run button handler
    if (runButton) {
        runButton.addEventListener('click', async function(e) {
            e.preventDefault();
            if (!isExecuting) {
                await executeCode();
            }
        });
    }

    isConsoleReady = true;
});