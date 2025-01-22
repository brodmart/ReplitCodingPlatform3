// Editor state and configuration
const editorState = {
    editor: null,
    isExecuting: false,
    currentLanguage: 'cpp',
    isInitialized: false,
    currentSession: null,
    isWaitingForInput: false,
    inputBuffer: '',
    inputCallback: null
};

// Set editor template with improved error handling and CSRF token
async function setEditorTemplate(language) {
    if (!language) {
        console.error('Language parameter is required');
        showError('Invalid language selection');
        return;
    }

    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            console.error('CSRF token not found');
            showError('Security token missing. Please refresh the page.');
            return;
        }

        console.log(`Setting template for language: ${language}`);
        const response = await fetch('/activities/get_template', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            },
            body: JSON.stringify({ language: language })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `Failed to load template (${response.status})`);
        }

        const data = await response.json();
        if (!data.success || !data.template) {
            throw new Error(data.error || 'Template not found');
        }

        if (editorState.editor) {
            editorState.editor.setValue(data.template);
            editorState.editor.clearHistory();
            // Position cursor appropriately based on language
            const cursorLine = language === 'cpp' ? 4 : 6;
            editorState.editor.setCursor(cursorLine, 4);
        } else {
            console.error('Editor not initialized');
            showError('Editor initialization failed');
        }
    } catch (error) {
        console.error('Error setting template:', error);
        showError(`Failed to change language: ${error.message}`);
        // Don't rethrow, we've handled the error with user feedback
    }
}

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

        // Initialize CodeMirror with basic configuration
        editorState.editor = CodeMirror.fromTextArea(editorElement, {
            mode: getEditorMode('cpp'), // Start with C++ as default
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

        // Set up event listeners
        setupEventListeners();

        // Get the language from the select element
        const languageSelect = document.getElementById('languageSelect');
        if (languageSelect) {
            editorState.currentLanguage = languageSelect.value || 'cpp';
            editorState.editor.setOption('mode', getEditorMode(editorState.currentLanguage));
        }

        // Try to load template
        try {
            await setEditorTemplate(editorState.currentLanguage);
        } catch (error) {
            console.warn('Failed to load template, using default:', error);
            const defaultTemplate = editorState.currentLanguage === 'cpp' 
                ? '#include <iostream>\n\nint main() {\n    // Your code here\n    return 0;\n}\n'
                : 'using System;\n\nclass Program {\n    static void Main() {\n        // Your code here\n    }\n}\n';
            editorState.editor.setValue(defaultTemplate);
        }

        // Mark editor as initialized
        editorState.isInitialized = true;
        console.log('Editor initialized successfully');

    } catch (error) {
        console.error('Editor initialization failed:', error);
        showError('Failed to initialize editor');
    }
}

// Get the appropriate mode for CodeMirror based on language
function getEditorMode(language) {
    const modes = {
        'cpp': 'text/x-c++src',
        'csharp': 'text/x-csharp'
    };
    return modes[language.toLowerCase()] || 'text/x-c++src';
}

// Set up event listeners
function setupEventListeners() {
    // Language selector
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', handleLanguageChange);
    }

    // Run button
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', runCode);
    }

    // Clear console button
    const clearButton = document.getElementById('clearConsole');
    if (clearButton) {
        clearButton.addEventListener('click', () => {
            const consoleOutput = document.getElementById('consoleOutput');
            if (consoleOutput) {
                consoleOutput.innerHTML = '';
            }
            editorState.inputBuffer = '';
            editorState.isWaitingForInput = false;
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
    if (!event.target) return;

    const newLanguage = event.target.value;
    if (!newLanguage || newLanguage === editorState.currentLanguage) return;

    console.log('Language changed to:', newLanguage);
    editorState.currentLanguage = newLanguage;
    editorState.editor.setOption('mode', getEditorMode(newLanguage));
    await setEditorTemplate(newLanguage);
}

// Show error message
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger position-fixed top-0 end-0 m-3';
    errorDiv.style.zIndex = '1050';
    errorDiv.textContent = message;
    document.body.appendChild(errorDiv);
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

// Run code with enhanced error handling and output
async function runCode() {
    if (editorState.isExecuting) return;

    const runButton = document.getElementById('runButton');
    const terminal = editorState.terminal;
    editorState.isExecuting = true;
    editorState.inputBuffer = '';
    editorState.isWaitingForInput = false;

    try {
        if (runButton) {
            runButton.disabled = true;
            runButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...';
        }

        const code = editorState.editor.getValue().trim();
        if (!code) {
            throw new Error('No code to execute');
        }

        terminal?.write('\r\n\x1b[33mCompiling and running code...\x1b[0m\r\n');

        const response = await fetch('/activities/run_code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
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
                if (result.waiting_for_input) {
                    editorState.isWaitingForInput = true;
                }
            }
        } else {
            const errorMsg = result.error || 'Unknown error occurred';
            terminal?.write('\x1b[31mError: ' + errorMsg + '\x1b[0m\r\n');
        }
    } catch (error) {
        console.error('Error executing code:', error);
        terminal?.write('\x1b[31mError: ' + error.message + '\x1b[0m\r\n');
    } finally {
        editorState.isExecuting = false;
        if (runButton) {
            runButton.disabled = false;
            runButton.innerHTML = 'Run';
        }
    }
}

// Poll for output from interactive sessions
async function startPollingOutput(sessionId) {
    const terminal = editorState.terminal;
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
                    if (result.waiting_for_input) {
                        editorState.isWaitingForInput = true;
                    }
                }

                if (result.session_ended) {
                    console.log('Session ended normally');
                    editorState.currentSession = null;
                    return;
                }

                // Continue polling if session is still active
                pollCount++;
                setTimeout(poll, 1000);
            } else {
                console.error('Error getting output:', result.error);
                editorState.currentSession = null;
            }
        } catch (error) {
            console.error('Error polling output:', error);
            editorState.currentSession = null;
        }
    };

    // Start polling
    poll();
}