// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;
let lastExecution = 0;
let isConsoleReady = false;

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

    try {
        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running...';
        }

        isExecuting = true;
        const code = editor.getValue().trim();
        const languageSelect = document.getElementById('languageSelect');
        const language = languageSelect ? languageSelect.value : 'cpp';

        // Get CSRF token
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            throw new Error('CSRF token not found. Please refresh the page.');
        }

        // Prepare request payload
        const payload = {
            code: code,
            language: language,
            activity_id: '' // Empty string as default
        };

        // Only add activity_id if we're in an activity context and it has a value
        const activityIdInput = document.querySelector('input[name="activity_id"]');
        if (activityIdInput && activityIdInput.value) {
            payload.activity_id = activityIdInput.value;
        }

        console.log('Executing code request:', {
            url: '/activities/run_code',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            },
            payload: JSON.stringify(payload, null, 2)
        });

        const response = await fetch('/activities/run_code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const responseText = await response.text();
        console.log('Raw server response:', responseText);

        let result;
        try {
            result = JSON.parse(responseText);
        } catch (e) {
            console.error('Failed to parse server response:', e);
            throw new Error('Invalid response format from server');
        }

        console.log('Parsed server response:', result);

        if (result.success) {
            if (consoleOutput) {
                let outputText = typeof result.output === 'string' ? result.output : JSON.stringify(result.output, null, 2);

                // If output is empty or undefined, show a message
                if (!outputText || outputText.trim() === '') {
                    outputText = 'Program executed successfully with no output.';
                }

                // For C# programs, ensure output is visible
                if (language === 'csharp' && outputText.includes('Program executed successfully with no output')) {
                    // Check if there's any actual output in the result
                    const actualOutput = result.output || '';
                    outputText = actualOutput.trim() || 'No output generated. If you expected output, ensure Console.WriteLine statements are used and properly flushed.';
                }

                consoleOutput.innerHTML = `<pre class="console-output">${escapeHtml(outputText)}</pre>`;
            }
        } else {
            let errorMessage = result.error;
            if (errorMessage === 'Missing required fields') {
                console.error('Missing fields in request:', payload);
                errorMessage = 'Required information is missing. Please check your code and try again.';
            }
            throw new Error(errorMessage || 'Failed to execute code');
        }
    } catch (error) {
        console.error('Error executing code:', error);
        if (consoleOutput) {
            let displayError = error.message;
            if (error.message.includes('HTTP error!')) {
                displayError = 'Code execution service is unavailable. Please try again in a moment.';
            } else if (error.message.includes('Invalid response format')) {
                displayError = 'Server returned an unexpected response. Please try again.';
            }
            consoleOutput.innerHTML = `<div class="console-error">Error: ${escapeHtml(displayError)}</div>`;
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
        mode: 'text/x-c++src',
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
    const currentCode = editor.getValue().trim();
    if (!currentCode) {
        const language = languageSelect ? languageSelect.value : 'cpp';
        editor.setValue(getTemplateForLanguage(language));
    }

    // Language change handler
    if (languageSelect) {
        languageSelect.addEventListener('change', () => {
            const language = languageSelect.value;
            editor.setOption('mode', language === 'cpp' ? 'text/x-c++src' : 'text/x-csharp');
            editor.setValue(getTemplateForLanguage(language));
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