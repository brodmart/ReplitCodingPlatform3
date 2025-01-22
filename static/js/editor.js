// Editor state and configuration
const editorState = {
    editor: null,
    isExecuting: false,
    currentLanguage: 'cpp',
    isInitialized: false,
    terminal: null,
    currentSession: null
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
            mode: getEditorMode(editorState.currentLanguage),
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

        // Get the language from the select element
        const languageSelect = document.getElementById('languageSelect');
        if (languageSelect) {
            editorState.currentLanguage = languageSelect.value;
        }

        // Set initial template
        await setEditorTemplate(editorState.currentLanguage);

        // Set up event listeners
        setupEventListeners();

        // Mark editor as initialized
        editorState.isInitialized = true;
        console.log('Editor initialized successfully');

    } catch (error) {
        console.error('Editor initialization failed:', error);
        showError('Failed to initialize editor: ' + error.message);
    }
}

// Get the appropriate mode for CodeMirror based on language
function getEditorMode(language) {
    const modes = {
        'cpp': 'text/x-c++src',
        'csharp': 'text/x-csharp'
    };
    return modes[language] || 'text/x-c++src';
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
    if (clearButton && window.terminal) {
        clearButton.addEventListener('click', () => {
            window.terminal.clear();
        });
    }

    // Auto-save editor content
    if (editorState.editor) {
        editorState.editor.on('change', () => {
            localStorage.setItem('editorContent', editorState.editor.getValue());
        });
    }
}

// Handle language change
async function handleLanguageChange(event) {
    const newLanguage = event.target.value;
    console.log('Language changed to:', newLanguage);

    if (newLanguage === editorState.currentLanguage) return;

    editorState.currentLanguage = newLanguage;
    editorState.editor.setOption('mode', getEditorMode(newLanguage));

    try {
        await setEditorTemplate(newLanguage);
    } catch (error) {
        console.error('Error setting template:', error);
        showError('Failed to set template for ' + newLanguage);
    }
}

// Set editor template
async function setEditorTemplate(language) {
    console.log('Setting template for language:', language);

    try {
        const response = await fetch('/activities/get_template', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
            },
            body: JSON.stringify({ language: language })
        });

        if (!response.ok) {
            throw new Error('Failed to fetch template');
        }

        const data = await response.json();
        if (data.success && data.template) {
            editorState.editor.setValue(data.template);
            editorState.editor.clearHistory();

            // Set cursor position after template is loaded
            const cursorLine = language === 'cpp' ? 4 : 6;
            editorState.editor.setCursor(cursorLine, 4);
        } else {
            throw new Error(data.error || 'Failed to get template');
        }
    } catch (error) {
        console.error('Error setting template:', error);
        throw error;
    }
}

// Run code with enhanced error handling and output
async function runCode() {
    if (editorState.isExecuting) return;

    const runButton = document.getElementById('runButton');
    const terminal = window.terminal;
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
                code,
                language: editorState.currentLanguage,
                session_id: editorState.currentSession
            })
        });

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const result = await response.json();

        if (result.success) {
            if (result.session_id && result.session_id !== editorState.currentSession) {
                editorState.currentSession = result.session_id;
                startPollingOutput(result.session_id);
            }

            if (result.output) {
                terminal?.write(result.output);
            }
        } else {
            const errorMsg = result.error || 'Unknown error occurred';
            terminal?.write('\x1b[31mError: ' + errorMsg + '\x1b[0m\r\n');
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

// Add language-specific error formatting
function formatCompilerError(error, language) {
    if (!error) return 'Unknown error occurred';

    switch (language.toLowerCase()) {
        case 'cpp':
            // Format C++ specific errors
            error = error.replace(/^In file included from.+\n?/gm, '');
            error = error.replace(/(\w+\.cpp):(\d+):(\d+):/g, 'Line $2, Column $3:');
            break;

        case 'csharp':
            // Format C# specific errors
            error = error.replace(/\((\d+),(\d+)\):/g, 'Line $1, Column $2:');
            error = error.replace(/error CS\d+:/g, 'Error:');
            break;
    }

    return error.trim();
}

// Poll for output from interactive sessions
async function startPollingOutput(sessionId) {
    const terminal = window.terminal;
    let pollCount = 0;
    const maxPolls = 300; // 5 minutes maximum

    const poll = async () => {
        if (pollCount >= maxPolls || !sessionId) {
            console.log('Session polling ended');
            return;
        }

        try {
            const response = await fetch('/activities/get_output', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
                },
                body: JSON.stringify({ session_id: sessionId })
            });

            if (!response.ok) {
                throw new Error('Failed to get output');
            }

            const result = await response.json();

            if (result.success) {
                if (result.output) {
                    terminal?.write(result.output);
                }

                if (result.session_ended) {
                    console.log('Session ended normally');
                    window.currentSession = null;
                    return;
                }

                // Continue polling if session is still active
                pollCount++;
                setTimeout(poll, 1000);
            } else {
                console.error('Error getting output:', result.error);
                window.currentSession = null;
            }
        } catch (error) {
            console.error('Error polling output:', error);
            window.currentSession = null;
        }
    };

    // Start polling
    poll();
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