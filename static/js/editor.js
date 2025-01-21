// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;
let lastExecution = 0;
let isConsoleReady = false;

// Update the executeCode function handling for C# interactive programs
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

    try {
        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running...';
        }

        isExecuting = true;
        const code = editor.getValue().trim();

        // Add code size validation
        if (code.length > 1000000) { // 1MB limit
            throw new Error('Code size exceeds maximum limit of 1MB');
        }

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
            language: language
        };

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

        const result = await response.json();
        console.log('Server response:', result);

        if (result.success) {
            if (result.interactive) {
                // Set up interactive console session
                let sessionId = result.session_id;
                consoleOutput.innerHTML = '';

                // Enable input handling
                if (consoleInput) {
                    consoleInput.disabled = false;
                    consoleInput.focus();

                    // Handle input submission
                    const handleInput = async (input) => {
                        if (input.trim() === '') return;

                        // Display input in console
                        const inputLine = document.createElement('div');
                        inputLine.className = 'console-input';
                        inputLine.textContent = `> ${input}`;
                        consoleOutput.appendChild(inputLine);

                        // Send input to server
                        try {
                            const inputResponse = await fetch('/activities/run_code', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRF-Token': csrfToken
                                },
                                body: JSON.stringify({
                                    session_id: sessionId,
                                    input: input + '\n'
                                })
                            });

                            if (inputResponse.ok) {
                                const inputResult = await inputResponse.json();
                                if (inputResult.success) {
                                    if (inputResult.output) {
                                        const outputElement = document.createElement('div');
                                        outputElement.className = 'console-output';
                                        outputElement.textContent = inputResult.output;
                                        consoleOutput.appendChild(outputElement);
                                    }

                                    // Auto-scroll to bottom
                                    consoleOutput.scrollTop = consoleOutput.scrollHeight;

                                    if (inputResult.session_ended) {
                                        consoleInput.disabled = true;
                                        sessionId = null;
                                    }
                                }
                            }
                        } catch (error) {
                            console.error('Error sending input:', error);
                            const errorElement = document.createElement('div');
                            errorElement.className = 'console-error';
                            errorElement.textContent = 'Error sending input: ' + error.message;
                            consoleOutput.appendChild(errorElement);
                        }

                        // Clear input field
                        consoleInput.value = '';
                    };

                    // Handle Enter key
                    consoleInput.onkeypress = (e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            const input = consoleInput.value;
                            handleInput(input);
                        }
                    };
                }

                // Start polling for output
                const pollOutput = async () => {
                    if (!sessionId) return;

                    try {
                        const outputResponse = await fetch('/activities/get_output', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRF-Token': csrfToken
                            },
                            body: JSON.stringify({ session_id: sessionId })
                        });

                        if (outputResponse.ok) {
                            const outputResult = await outputResponse.json();
                            if (outputResult.success && outputResult.output) {
                                const outputElement = document.createElement('div');
                                outputElement.className = 'console-output';
                                outputElement.textContent = outputResult.output;
                                consoleOutput.appendChild(outputElement);
                                consoleOutput.scrollTop = consoleOutput.scrollHeight;
                            }

                            if (!outputResult.session_ended) {
                                setTimeout(pollOutput, 100);
                            } else {
                                consoleInput.disabled = true;
                                sessionId = null;
                            }
                        }
                    } catch (error) {
                        console.error('Error polling output:', error);
                    }
                };

                // Start polling
                pollOutput();
            } else {
                // Handle non-interactive output
                if (consoleOutput) {
                    consoleOutput.innerHTML = `<pre class="console-output">${escapeHtml(result.output || '')}</pre>`;
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
            runButton.innerHTML = '<i class="bi bi-play-fill"></i> Run';
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
}
`;
    } else {
        return `using System;

class Program 
{
    static void Main(string[] args)
    {
        Console.WriteLine("Hello World!");
    }
}
`;
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

            // Only reset code if it's empty or contains the template
            const currentCode = editor.getValue().trim();
            if (!currentCode || currentCode === getTemplateForLanguage(language === 'cpp' ? 'csharp' : 'cpp')) {
                editor.setValue(getTemplateForLanguage(language));
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