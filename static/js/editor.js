// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;
let activeProcess = null;

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', async function() {
    try {
        await waitForConsoleClass();
        await initializeComponents();
    } catch (error) {
        console.error('Failed to initialize editor:', error);
        showError('Failed to initialize editor. Please refresh the page.');
    }
});

async function waitForConsoleClass(maxAttempts = 10) {
    return new Promise((resolve, reject) => {
        let attempts = 0;
        const check = () => {
            if (typeof InteractiveConsole !== 'undefined') {
                resolve();
            } else if (attempts >= maxAttempts) {
                reject(new Error('Console class not loaded after maximum attempts'));
            } else {
                attempts++;
                setTimeout(check, 500);
            }
        };
        check();
    });
}

async function initializeComponents() {
    try {
        await initializeEditor();
        await initializeConsole();
        setupEventListeners();
        setInitialEditorState();
        console.log('Editor and console initialized successfully');
    } catch (error) {
        console.error('Failed to initialize components:', error);
        throw error;
    }
}

async function initializeEditor() {
    const editorElement = document.getElementById('editor');
    if (!editorElement) {
        throw new Error('Editor element not found');
    }

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
        gutters: ["CodeMirror-linenumbers", "CodeMirror-lint-markers", "CodeMirror-foldgutter"],
        extraKeys: {
            "Tab": function(cm) {
                if (cm.somethingSelected()) {
                    cm.indentSelection("add");
                } else {
                    cm.replaceSelection("    ", "end");
                }
            },
            "Ctrl-Enter": executeCode,
            "Cmd-Enter": executeCode,
            "Ctrl-/": "toggleComment",
            "Cmd-/": "toggleComment",
            "Ctrl-S": function(cm) {
                // Auto-save is already happening
                return false;
            },
            "Cmd-S": function(cm) {
                // Auto-save is already happening
                return false;
            }
        },
        foldGutter: true,
        lint: {
            delay: 800,
            async: true
        },
        autoCloseTags: true,
        matchTags: {bothTags: true},
        autoRefresh: true,
        placeholder: "Type your code here..."
    });

    // Set up editor change handler with debouncing
    let saveTimeout;
    editor.on('change', function() {
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(() => {
            localStorage.setItem('editorContent', editor.getValue());
        }, 500);
    });

    return new Promise((resolve) => {
        editor.refresh();
        editor.getWrapperElement().classList.add('CodeMirror-initialized');
        resolve();
    });
}

async function initializeConsole() {
    try {
        if (typeof InteractiveConsole === 'undefined') {
            throw new Error('Console class not loaded');
        }

        const elements = await waitForConsoleElements();

        consoleInstance = new InteractiveConsole({
            outputElement: elements.output,
            inputElement: elements.input,
            onCommand: handleConsoleCommand,
            onInput: handleConsoleInput,
            onClear: () => {
                if (activeProcess) {
                    activeProcess.terminate();
                    activeProcess = null;
                }
            }
        });

        const savedContent = localStorage.getItem('editorContent');
        if (savedContent && editor) {
            editor.setValue(savedContent);
        }

    } catch (error) {
        console.error('Failed to initialize console:', error);
        throw error;
    }
}

function waitForConsoleElements(maxRetries = 10, interval = 100) {
    return new Promise((resolve, reject) => {
        let attempts = 0;

        const checkElements = () => {
            const output = document.getElementById('consoleOutput');
            const input = document.getElementById('consoleInput');

            if (output && input) {
                resolve({ output, input });
            } else if (attempts >= maxRetries) {
                reject(new Error('Console elements not found after maximum retries'));
            } else {
                attempts++;
                setTimeout(checkElements, interval);
            }
        };

        checkElements();
    });
}

async function handleConsoleCommand(command) {
    if (!editor || !consoleInstance) return;

    try {
        const response = await executeCommand(command);
        consoleInstance.appendOutput(response);
    } catch (error) {
        consoleInstance.appendError(`Error: ${error.message}`);
    }
}

async function handleConsoleInput(input) {
    if (activeProcess) {
        activeProcess.sendInput(input);
    }
}

async function executeCommand(command) {
    const languageSelect = document.getElementById('languageSelect');
    const language = languageSelect ? languageSelect.value : 'cpp';

    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            throw new Error('CSRF token not found');
        }

        const response = await fetch('/execute_command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            },
            body: JSON.stringify({ command, language })
        });

        if (!response.ok) {
            throw new Error('Failed to execute command');
        }

        return response.text();
    } catch (error) {
        console.error('Execute command error:', error);
        throw error;
    }
}

async function executeCode() {
    if (!editor || !consoleInstance || isExecuting) {
        return;
    }

    const runButton = document.getElementById('runButton');
    isExecuting = true;

    try {
        updateRunButtonState(true);
        consoleInstance.clear();
        consoleInstance.disable();
        consoleInstance.appendOutput('Compiling and running code...\n');

        const code = editor.getValue().trim();
        if (!code) {
            throw new Error('No code to execute');
        }

        const languageSelect = document.getElementById('languageSelect');
        const language = languageSelect ? languageSelect.value : 'cpp';
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
            body: JSON.stringify({ code, language })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();

        if (result.success) {
            handleSuccessfulExecution(result);
        } else {
            handleFailedExecution(result.error);
        }
    } catch (error) {
        console.error('Error executing code:', error);
        handleExecutionError(error.message);
    } finally {
        cleanupExecution();
    }
}

function handleSuccessfulExecution(result) {
    consoleInstance.clear();
    consoleInstance.appendSuccess('Compilation successful!\n');

    if (result.output) {
        consoleInstance.appendOutput(result.output);
    }

    if (result.warnings) {
        result.warnings.forEach(warning => {
            const line = warning.line - 1;
            editor.addLineClass(line, 'background', 'line-warning');
            consoleInstance.appendOutput(`Warning (line ${warning.line}): ${warning.message}\n`, 'warning');
        });
    }
}

function handleFailedExecution(error) {
    // Clear previous error markers
    editor.getAllMarks().forEach(mark => mark.clear());
    editor.clearGutter("CodeMirror-lint-markers");

    // Parse error message to extract line number if available
    const errorMatch = error.match(/line (\d+)/i);
    if (errorMatch) {
        const lineNum = parseInt(errorMatch[1]) - 1;
        markErrorLine(lineNum, error);
    }

    consoleInstance.appendError(error);
}

function markErrorLine(lineNum, errorMessage) {
    const marker = document.createElement('div');
    marker.className = 'CodeMirror-lint-marker CodeMirror-lint-marker-error';
    marker.title = errorMessage;

    editor.setGutterMarker(lineNum, "CodeMirror-lint-markers", marker);
    editor.addLineClass(lineNum, 'background', 'line-error');

    // Scroll to error line
    editor.scrollIntoView({line: lineNum, ch: 0}, 100);
}

function handleExecutionError(error) {
    consoleInstance.appendError(`Runtime Error: ${error}`);
}

function cleanupExecution() {
    isExecuting = false;
    updateRunButtonState(false);
    consoleInstance.enable();
    activeProcess = null;
}

function updateRunButtonState(running) {
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.disabled = running;
        runButton.innerHTML = running ?
            '<span class="spinner-border spinner-border-sm"></span> Running...' :
            'Run';
    }
}

function setupEventListeners() {
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', function(e) {
            e.preventDefault();
            if (!isExecuting) {
                executeCode();
            }
        });
    }

    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const language = this.value;
            updateEditorMode(language);
            setEditorTemplate(language);
            localStorage.setItem('selectedLanguage', language);
        });
    }

    const clearButton = document.getElementById('clearConsole');
    if (clearButton) {
        clearButton.addEventListener('click', function() {
            if (consoleInstance) {
                consoleInstance.clear();
            }
        });
    }
}

function updateEditorMode(language) {
    if (!editor) return;

    const modes = {
        'cpp': 'text/x-c++src',
        'csharp': 'text/x-csharp'
    };

    editor.setOption('mode', modes[language] || modes.cpp);
}

function setEditorTemplate(language) {
    if (!editor) return;
    const template = getTemplateForLanguage(language);
    editor.setValue(template);
    editor.setCursor(editor.lineCount() - 2, 0);
}

function getTemplateForLanguage(language) {
    const templates = {
        'cpp': `#include <iostream>
using namespace std;

int main() {
    // Your C++ code here
    cout << "Hello World!" << endl;
    return 0;
}`,
        'csharp': `using System;

class Program 
{
    static void Main(string[] args)
    {
        // Your C# code here
        Console.WriteLine("Hello World!");
    }
}`
    };

    return templates[language] || templates.cpp;
}

function setInitialEditorState() {
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        const savedLanguage = localStorage.getItem('selectedLanguage') || 'cpp';
        languageSelect.value = savedLanguage;
        updateEditorMode(savedLanguage);

        const savedContent = localStorage.getItem('editorContent');
        if (!savedContent) {
            setEditorTemplate(savedLanguage);
        }
    }
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger';
    errorDiv.textContent = message;
    document.body.insertBefore(errorDiv, document.body.firstChild);
    setTimeout(() => errorDiv.remove(), 5000);
}