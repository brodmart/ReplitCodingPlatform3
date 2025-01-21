// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;
let lastExecution = 0;
let isConsoleReady = false;

document.addEventListener('DOMContentLoaded', function() {
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
            }
        }
    });

    // Only set template if editor is empty
    if (!editor.getValue().trim()) {
        const language = languageSelect ? languageSelect.value : 'cpp';
        editor.setValue(getTemplateForLanguage(language));
    }

    // Language change handler
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const language = languageSelect.value;

            // Set appropriate mode for CodeMirror
            if (language === 'cpp') {
                editor.setOption('mode', 'text/x-c++src');
            } else if (language === 'csharp') {
                editor.setOption('mode', 'text/x-csharp');
            }

            // Get current code and new template
            const currentCode = editor.getValue().trim();
            const newTemplate = getTemplateForLanguage(language);

            // Check if current code matches any template
            const cppTemplate = getTemplateForLanguage('cpp');
            const csharpTemplate = getTemplateForLanguage('csharp');

            // Only replace code if it matches a template or is empty
            if (!currentCode || currentCode === cppTemplate || currentCode === csharpTemplate) {
                editor.setValue(newTemplate);
            }
        });
    }

    // Run button handler
    if (runButton) {
        runButton.addEventListener('click', async function(e) {
            e.preventDefault();
            if (!isExecuting) {
                await executeCode();
            }
        });
    }

    // Keyboard shortcut
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !isExecuting) {
            e.preventDefault();
            executeCode();
        }
    });

    isConsoleReady = true;
});

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

// Execute Code Function
async function executeCode() {
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
    const consoleInput = document.getElementById('consoleInput');
    const languageSelect = document.getElementById('languageSelect');

    try {
        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running...';
        }

        isExecuting = true;
        const code = editor.getValue().trim();
        const language = languageSelect ? languageSelect.value : 'cpp';

        // Add code size validation
        if (code.length > 1000000) { // 1MB limit
            throw new Error('Code size exceeds maximum limit of 1MB');
        }

        // Get CSRF token
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            throw new Error('CSRF token not found. Please refresh the page.');
        }

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

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        console.log('Server response:', result);

        if (result.success) {
            if (result.output) {
                if (consoleOutput) {
                    consoleOutput.innerHTML = `<pre class="console-output">${escapeHtml(result.output)}</pre>`;
                }
            }
        } else {
            throw new Error(result.error || 'Failed to execute code');
        }
    } catch (error) {
        console.error('Error executing code:', error);
        if (consoleOutput) {
            let displayError = error.message;
            if (error.message.includes('HTTP error!')) {
                displayError = 'Code execution service is unavailable. Please try again in a moment.';
            }
            consoleOutput.innerHTML = `<div class="console-error">Error: ${escapeHtml(displayError)}</div>`;
        }
    } finally {
        isExecuting = false;
        if (runButton) {
            runButton.disabled = false;
            runButton.innerHTML = 'Run';
        }
    }
}

// Helper function to format C# errors
function formatCSharpError(errorMsg) {
    try {
        // Extract line number and error message
        const match = errorMsg.match(/\((\d+),(\d+)\):\s*(error\s*CS\d+):\s*(.+)/);
        if (match) {
            const [_, line, column, errorCode, message] = match;
            return `${errorCode} at line ${line}, column ${column}:\n${message}`;
        }
    } catch (e) {
        console.error('Error formatting C# error:', e);
    }
    return errorMsg;
}

// Helper function to escape HTML
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}