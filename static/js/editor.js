// Editor state and configuration
const editorState = {
    editor: null,
    isExecuting: false,
    currentLanguage: 'csharp',
    isInitialized: false,
    terminal: null,
    templates: {
        cpp: `#include <iostream>
using namespace std;

int main() {
    // Your C++ code here
    cout << "Hello World!" << endl;
    return 0;
}`,
        csharp: `using System;

class Program 
{
    static void Main(string[] args)
    {
        // Your C# code here
        Console.WriteLine("Hello World!");
    }
}`
    }
};

// Initialize editor with proper error handling
async function initializeEditor() {
    try {
        // Prevent multiple initializations
        if (editorState.isInitialized) {
            console.log('Editor already initialized');
            return;
        }

        const editorElement = document.getElementById('editor');
        if (!editorElement) {
            throw new Error('Editor element not found');
        }

        // Initialize CodeMirror with error handling
        editorState.editor = CodeMirror.fromTextArea(editorElement, {
            mode: 'text/x-csharp',  // Default to C# mode
            theme: 'dracula',
            lineNumbers: true,
            autoCloseBrackets: true,
            matchBrackets: true,
            indentUnit: 4,
            tabSize: 4,
            lineWrapping: true,
            extraKeys: {
                "Tab": function(cm) {
                    if (cm.somethingSelected()) {
                        cm.indentSelection("add");
                    } else {
                        cm.replaceSelection("    ", "end");
                    }
                },
                "Ctrl-Enter": runCode,
                "Cmd-Enter": runCode
            }
        });

        // Initialize xterm.js
        const terminal = new Terminal({
            cursorBlink: true,
            theme: {
                background: '#282a36',
                foreground: '#f8f8f2'
            },
            fontSize: 14,
            fontFamily: 'Menlo, Monaco, "Courier New", monospace',
            rows: 10,
            scrollback: 1000,
            convertEol: true
        });

        const fitAddon = new FitAddon.FitAddon();
        terminal.loadAddon(fitAddon);

        const terminalElement = document.getElementById('terminal');
        if (!terminalElement) {
            throw new Error('Terminal element not found');
        }

        terminal.open(terminalElement);
        fitAddon.fit();

        // Handle terminal resize
        window.addEventListener('resize', () => {
            fitAddon.fit();
        });

        // Store terminal instance
        editorState.terminal = terminal;
        window.terminal = terminal;  // Make terminal accessible globally

        // Set up event listeners
        setupEventListeners();

        // Set initial template only if editor is empty
        const savedContent = localStorage.getItem('editorContent');
        if (!savedContent) {
            setEditorTemplate(editorState.currentLanguage);
        } else {
            editorState.editor.setValue(savedContent);
        }

        // Mark editor as initialized
        editorState.isInitialized = true;
        console.log('Editor and terminal initialized successfully');

    } catch (error) {
        console.error('Editor initialization failed:', error);
        showError('Failed to initialize editor: ' + error.message);
    }
}

// Set up event listeners
function setupEventListeners() {
    // Run button
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', runCode);
    }

    // Language selector
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', handleLanguageChange);
        // Set initial language
        editorState.currentLanguage = languageSelect.value;
    }

    // Clear console button
    const clearButton = document.getElementById('clearConsole');
    if (clearButton && editorState.terminal) {
        clearButton.addEventListener('click', () => {
            editorState.terminal.clear();
        });
    }

    // Auto-save editor content
    if (editorState.editor) {
        editorState.editor.on('change', () => {
            localStorage.setItem('editorContent', editorState.editor.getValue());
        });
    }
}

// Run code with enhanced error handling and output
async function runCode() {
    if (editorState.isExecuting) return;

    const runButton = document.getElementById('runButton');
    const terminal = editorState.terminal;
    editorState.isExecuting = true;

    try {
        console.time('codeExecution');
        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...';
        }

        const code = editorState.editor.getValue().trim();
        if (!code) {
            throw new Error('No code to execute');
        }

        terminal?.write('\r\n\x1b[33mCompiling and running code...\x1b[0m\r\n');
        console.log('Code length:', code.length, 'bytes');

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            throw new Error('CSRF token not found');
        }

        console.log('Sending request to server...');
        const response = await fetch('/activities/run_code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            },
            body: JSON.stringify({ 
                code, 
                language: editorState.currentLanguage 
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        console.log('Received response:', result);

        if (result.success) {
            terminal?.write('\r\n\x1b[32mCompilation successful!\x1b[0m\r\n');
            if (result.output) {
                terminal?.write(result.output + '\r\n');
            }
            if (result.metrics) {
                console.log('Performance metrics:', result.metrics);
            }
        } else {
            terminal?.write('\x1b[31mError: ' + (result.error || 'Unknown error occurred') + '\x1b[0m\r\n');
            if (result.metrics) {
                console.log('Error metrics:', result.metrics);
            }
        }
    } catch (error) {
        console.error('Error executing code:', error);
        terminal?.write('\x1b[31mError: ' + error.message + '\x1b[0m\r\n');
    } finally {
        console.timeEnd('codeExecution');
        editorState.isExecuting = false;
        if (runButton) {
            runButton.disabled = false;
            runButton.innerHTML = 'Run';
        }
    }
}

// Handle language change
function handleLanguageChange(event) {
    const newLanguage = event.target.value;
    if (newLanguage === editorState.currentLanguage) return;

    editorState.currentLanguage = newLanguage;
    const modes = {
        'cpp': 'text/x-c++src',
        'csharp': 'text/x-csharp'
    };

    editorState.editor.setOption('mode', modes[newLanguage]);

    // Check if there's existing content
    const currentContent = editorState.editor.getValue().trim();
    const isTemplateContent = Object.values(editorState.templates).some(template => 
        currentContent === template.trim()
    );

    if (!currentContent || isTemplateContent) {
        setEditorTemplate(newLanguage);
    }

    editorState.editor.refresh();
}

// Set editor template
function setEditorTemplate(language) {
    const template = editorState.templates[language] || '';
    if (!template) {
        console.error('Template not found for language:', language);
        return;
    }

    editorState.editor.setValue('');
    editorState.editor.clearHistory();
    editorState.editor.setValue(template);

    const cursorLine = language === 'cpp' ? 5 : 7;
    editorState.editor.setCursor(cursorLine, 4);
}

// Show error message
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger';
    errorDiv.textContent = message;
    document.body.insertBefore(errorDiv, document.body.firstChild);
    setTimeout(() => errorDiv.remove(), 5000);
}

// Initialize everything when the DOM is ready
document.addEventListener('DOMContentLoaded', async function() {
    try {
        await initializeEditor();
    } catch (error) {
        console.error('Failed to initialize editor:', error);
        showError('Failed to initialize editor. Please refresh the page.');
    }
});