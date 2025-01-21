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

    // Enhanced CodeMirror initialization with educational features
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
            },
            "Ctrl-Space": "autocomplete",
            "Ctrl-/": "toggleComment",
            "Ctrl-F": "findPersistent"
        },
        // Educational features
        highlightSelectionMatches: {showToken: /\w/, annotateScrollbar: true},
        matchTags: {bothTags: true},
        autoCloseTags: true,
        lint: true,
        hintOptions: {
            completeSingle: false,
            extraKeys: {
                "Ctrl-Space": "autocomplete"
            }
        }
    });

    // Enhance the language change handler
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const language = languageSelect.value;
            console.log('Language changed to:', language);

            // Update editor mode and settings based on language
            if (language === 'cpp') {
                editor.setOption('mode', 'text/x-c++src');
                editor.setOption('lint', {
                    'esversion': 6,
                    'asi': true
                });
            } else if (language === 'csharp') {
                editor.setOption('mode', 'text/x-csharp');
                editor.setOption('lint', {
                    'esversion': 6,
                    'asi': true
                });
            }

            // Only update template if current content is empty or matches a template
            const currentCode = editor.getValue().trim();
            const isCppTemplate = currentCode === getTemplateForLanguage('cpp').trim();
            const isCsharpTemplate = currentCode === getTemplateForLanguage('csharp').trim();

            if (!currentCode || isCppTemplate || isCsharpTemplate) {
                editor.setValue(getTemplateForLanguage(language));
            }
        });
    }

    // Enhanced error handling and execution
    if (runButton) {
        let executionTimeout;
        runButton.addEventListener('click', async function(e) {
            e.preventDefault();
            if (isExecuting) {
                console.log('Already executing code');
                return;
            }

            // Clear any existing timeout
            if (executionTimeout) {
                clearTimeout(executionTimeout);
            }

            const now = Date.now();
            if (now - lastExecution < 2000) { // 2 second cooldown
                console.log('Execution throttled');
                return;
            }

            await executeCode();
        });
    }

    // Add keyboard shortcuts for educational features
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !isExecuting) {
            e.preventDefault();
            executeCode();
        }
        // Add educational shortcut keys
        if (e.ctrlKey && e.key === 'h') { // Help shortcut
            e.preventDefault();
            showHelp();
        }
    });

    // Initialize error checking
    editor.on('change', function(cm, change) {
        clearTimeout(editor.lintTimeout);
        editor.lintTimeout = setTimeout(function() {
            updateErrorHighlighting(cm);
        }, 500);
    });

    isConsoleReady = true;
});

// Enhanced template function
function getTemplateForLanguage(language) {
    if (language === 'cpp') {
        return `#include <iostream>
#include <string>
using namespace std;

int main() {
    // This is a simple C++ program
    string message = "Hello World!";
    cout << message << endl;

    // Get user input
    string name;
    cout << "Enter your name: ";
    getline(cin, name);
    cout << "Hello, " << name << "!" << endl;

    return 0;
}`;
    } else if (language === 'csharp') {
        return `using System;

class Program 
{
    static void Main(string[] args)
    {
        // This is a simple C# program
        string message = "Hello World!";
        Console.WriteLine(message);

        // Get user input
        Console.Write("Enter your name: ");
        string name = Console.ReadLine();
        Console.WriteLine($"Hello, {name}!");
    }
}`;
    }
    return ''; // Default empty template
}

// New function for error highlighting
function updateErrorHighlighting(cm) {
    const code = cm.getValue();
    const language = document.getElementById('languageSelect')?.value || 'cpp';

    // Clear existing error markers
    cm.clearGutter('CodeMirror-lint-markers');

    // Basic syntax checking (placeholder - replace with actual implementation)
    let errors = [];
    if (language === 'cpp') {
        errors = checkCppSyntax(code);
    } else if (language === 'csharp') {
        errors = checkCSharpSyntax(code);
    }

    // Mark errors in the editor
    errors.forEach(error => {
        cm.setGutterMarker(error.line, 'CodeMirror-lint-markers', makeMarker(error.message));
    });
}

// Helper function for error markers
function makeMarker(msg) {
    const marker = document.createElement('div');
    marker.classList.add('CodeMirror-lint-marker');
    marker.title = msg;
    return marker;
}

// Execute Code Function with improved error handling
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
    const languageSelect = document.getElementById('languageSelect');

    let executionTimeout;

    try {
        isExecuting = true;
        lastExecution = Date.now();

        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running...';
        }

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

        // Set execution timeout - 60 seconds for C#, 30 for others
        const timeoutDuration = language === 'csharp' ? 60000 : 30000;
        const timeoutPromise = new Promise((_, reject) => {
            executionTimeout = setTimeout(() => {
                reject(new Error('Execution timeout'));
            }, timeoutDuration);
        });

        // Execute code with timeout
        const executionPromise = fetch('/activities/run_code', {
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

        const response = await Promise.race([executionPromise, timeoutPromise]);
        clearTimeout(executionTimeout);

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
            if (error.message.includes('timeout')) {
                displayError = 'Code execution timed out. Please check for infinite loops or reduce the code complexity.';
            } else if (error.message.includes('HTTP error!')) {
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
        if (executionTimeout) {
            clearTimeout(executionTimeout);
        }
    }
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