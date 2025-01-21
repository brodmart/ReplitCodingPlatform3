// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;
let lastExecution = 0;
let isConsoleReady = false;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize CodeMirror with basic settings first
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
        foldGutter: true,
        gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
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

    // Make editor visible immediately after initialization
    editor.getWrapperElement().classList.add('CodeMirror-initialized');

    // Get language select and set initial template
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        const initialLanguage = languageSelect.value;
        updateEditorMode(initialLanguage);
        setEditorTemplate(initialLanguage);

        // Language change handler with debugging
        languageSelect.addEventListener('change', function(event) {
            const language = event.target.value;
            console.log('Language changed to:', language);
            updateEditorMode(language);
            setEditorTemplate(language);

            // Force editor refresh after mode change
            editor.refresh();
        });
    }

    // Run button handler - using both possible IDs
    const runButton = document.getElementById('runButton') || document.getElementById('runCode');
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

function setEditorTemplate(language) {
    if (!editor) {
        console.error('Editor not initialized');
        return;
    }

    const currentCode = editor.getValue().trim();
    if (!currentCode) {
        const template = getTemplateForLanguage(language);
        console.log('Setting template for', language, ':', template);
        editor.setValue(template);
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

async function executeCode() {
    if (!editor || !isConsoleReady || isExecuting) {
        console.error('Execute prevented:', {
            hasEditor: !!editor,
            isConsoleReady,
            isExecuting
        });
        return;
    }

    const runButton = document.getElementById('runButton') || document.getElementById('runCode');
    const consoleOutput = document.getElementById('consoleOutput');
    const languageSelect = document.getElementById('languageSelect');

    try {
        isExecuting = true;
        lastExecution = Date.now();

        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running...';
        }

        const code = editor.getValue().trim();
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
            body: JSON.stringify({
                code: code,
                language: language
            })
        });

        const result = await response.json();

        if (result.success) {
            if (consoleOutput && result.output) {
                consoleOutput.innerHTML = `<pre class="console-output">${escapeHtml(result.output)}</pre>`;
            }
        } else {
            throw new Error(result.error || 'Failed to execute code');
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
            runButton.innerHTML = 'Run';
        }
    }
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Placeholder functions for syntax checking -  Replace with actual implementation
function checkCppSyntax(code) {
    // Implement C++ syntax checking logic here.  Return an array of error objects:  [{line: 10, message: "Syntax error"}, ...]
    return [];
}

function checkCSharpSyntax(code) {
    // Implement C# syntax checking logic here. Return an array of error objects:  [{line: 10, message: "Syntax error"}, ...]
    return [];
}

function showHelp() {
    //Implement help functionality here.  Alert for now.
    alert("Help: Ctrl+Space for autocomplete, Ctrl+/ for commenting, Ctrl+F for find.");
}