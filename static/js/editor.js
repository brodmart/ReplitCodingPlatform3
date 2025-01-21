// Initialize console instance at the global scope
let consoleInstance = null;
let editor = null;
let isExecuting = false;

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', async function() {
    await initializeComponents();
});

async function initializeComponents() {
    try {
        // Initialize editor first
        await initializeEditor();

        // Then initialize console
        await initializeConsole();

        // Setup event listeners after both components are ready
        setupEventListeners();

        // Set initial editor state
        setInitialEditorState();

    } catch (error) {
        console.error('Failed to initialize components:', error);
        showError('Failed to initialize editor. Please try again.');
    }
}

async function initializeEditor() {
    const editorElement = document.getElementById('editor');
    if (!editorElement) {
        throw new Error('Editor element not found');
    }

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
            "Cmd-/": "toggleComment"
        },
        foldGutter: true,
        lint: true,
        autoCloseTags: true,
        matchTags: {bothTags: true},
        autoRefresh: true
    });

    // Set up editor change handler
    editor.on('change', function() {
        localStorage.setItem('editorContent', editor.getValue());
    });

    return new Promise((resolve) => {
        editor.refresh();
        editor.getWrapperElement().classList.add('CodeMirror-initialized');
        resolve();
    });
}

async function initializeConsole() {
    try {
        // Ensure Console class is loaded
        if (typeof InteractiveConsole === 'undefined') {
            throw new Error('Console class not loaded');
        }

        // Wait for console elements
        const elements = await waitForConsoleElements();

        // Initialize console instance
        consoleInstance = new InteractiveConsole({
            outputElement: elements.output,
            inputElement: elements.input,
            onCommand: handleConsoleCommand
        });

        // Restore previous content if any
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
        consoleInstance.appendOutput(`Error: ${error.message}`, 'error');
    }
}

async function executeCommand(command) {
    const languageSelect = document.getElementById('languageSelect');
    const language = languageSelect ? languageSelect.value : 'cpp';

    const response = await fetch('/execute_command', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content
        },
        body: JSON.stringify({ command, language })
    });

    if (!response.ok) {
        throw new Error('Failed to execute command');
    }

    return response.text();
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger';
    errorDiv.textContent = message;
    document.body.insertBefore(errorDiv, document.body.firstChild);

    // Auto-remove after 5 seconds
    setTimeout(() => errorDiv.remove(), 5000);
}

function setupEventListeners() {
    // Run button handler
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', function(e) {
            e.preventDefault();
            if (!isExecuting) {
                executeCode();
            }
        });
    }

    // Language select handler with improved mode switching
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const language = this.value;
            updateEditorMode(language);
            setEditorTemplate(language);

            // Store selected language
            localStorage.setItem('selectedLanguage', language);
        });
    }

    // Add keyboard shortcuts listener
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + S to prevent default save
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            // Auto-save is already happening on change
        }
    });
}

function setInitialEditorState() {
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        // Restore previously selected language or default to cpp
        const savedLanguage = localStorage.getItem('selectedLanguage') || 'cpp';
        languageSelect.value = savedLanguage;
        updateEditorMode(savedLanguage);
        setEditorTemplate(savedLanguage);
    }
}

async function executeCode() {
    if (!editor || !consoleInstance) {
        console.error('Editor or console not initialized');
        return;
    }

    if (isExecuting) {
        return;
    }

    const runButton = document.getElementById('runButton');
    isExecuting = true;

    try {
        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...';
        }

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
            consoleInstance.clear();
            consoleInstance.appendOutput('Compilation successful!\n', 'success');
            if (result.output) {
                consoleInstance.appendOutput(result.output);
            }

            // Highlight any warnings
            if (result.warnings) {
                result.warnings.forEach(warning => {
                    const line = warning.line - 1;
                    editor.addLineClass(line, 'background', 'line-warning');
                });
            }
        } else {
            handleCompilationError(result.error);
        }
    } catch (error) {
        console.error('Error executing code:', error);
        handleExecutionError(error.message);
    } finally {
        isExecuting = false;
        if (runButton) {
            runButton.disabled = false;
            runButton.innerHTML = 'Run';
        }
        consoleInstance.enable();
    }
}

function handleCompilationError(error) {
    // Clear previous error markers
    editor.clearGutter("CodeMirror-lint-markers");

    // Parse error message to extract line number if available
    const errorMatch = error.match(/line (\d+)/i);
    if (errorMatch) {
        const lineNum = parseInt(errorMatch[1]) - 1;
        const marker = document.createElement('div');
        marker.className = 'CodeMirror-lint-marker CodeMirror-lint-marker-error';
        marker.title = error;
        editor.setGutterMarker(lineNum, "CodeMirror-lint-markers", marker);
        editor.addLineClass(lineNum, 'background', 'line-error');
    }

    consoleInstance.setError(error);
}

function handleExecutionError(error) {
    consoleInstance.setError(`Runtime Error: ${error}`);
}

function updateEditorMode(language) {
    if (!editor) return;

    const modes = {
        'cpp': 'text/x-c++src',
        'csharp': 'text/x-csharp'
    };

    editor.setOption('mode', modes[language] || modes.cpp);

    // Update lint options based on language
    editor.setOption('lint', {
        'cpp': {
            esversion: 6,
            asi: true
        },
        'csharp': {
            esversion: 6,
            asi: true
        }
    }[language] || {});
}

function setEditorTemplate(language) {
    if (!editor) return;
    const template = getTemplateForLanguage(language);
    editor.setValue(template);
    editor.setCursor(editor.lineCount() - 2, 0); // Position cursor at second to last line
}

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
    return '';
}