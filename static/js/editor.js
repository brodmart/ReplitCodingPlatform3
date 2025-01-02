// Initialize CodeMirror editor with default settings
document.addEventListener('DOMContentLoaded', function() {
    const editorElement = document.getElementById('editor');
    if (!editorElement) {
        console.error('Editor element not found');
        return;
    }

    // Get initial code from the textarea
    const initialCode = editorElement.value;

    // Initialize CodeMirror
    const editor = CodeMirror.fromTextArea(editorElement, {
        mode: 'text/x-c++src',
        theme: 'dracula',
        lineNumbers: true,
        autoCloseBrackets: true,
        matchBrackets: true,
        indentUnit: 4,
        tabSize: 4,
        lineWrapping: true,
        extraKeys: {"Ctrl-Space": "autocomplete"}
    });

    // Set initial code and refresh editor
    editor.setValue(initialCode || getTemplateForLanguage('cpp'));
    editor.refresh();

    // Track if code has been executed and modified
    let hasExecuted = false;
    let isModified = false;

    // Store initial template for comparison
    let currentTemplate = getTemplateForLanguage('cpp');

    // Handle language changes
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        const initialLanguage = languageSelect.value || 'cpp';
        editor.setOption('mode', getEditorMode(initialLanguage));

        languageSelect.addEventListener('change', function() {
            const language = this.value;
            const currentCode = editor.getValue().trim();

            // Always update the editor mode for proper syntax highlighting
            editor.setOption('mode', getEditorMode(language));

            // Reset to template if:
            // 1. Code has been executed
            // 2. Current code matches other language's characteristics
            // 3. Editor is empty
            if (hasExecuted || shouldUseTemplate(currentCode, language) || !currentCode) {
                const newTemplate = getTemplateForLanguage(language);
                editor.setValue(newTemplate);
                currentTemplate = newTemplate;
                isModified = false;
                hasExecuted = false;
            }

            editor.refresh();
        });
    }

    // Handle code changes
    editor.on('change', function() {
        const currentCode = editor.getValue().trim();
        isModified = currentCode !== currentTemplate.trim();
    });

    // Helper function to get editor mode based on language
    function getEditorMode(language) {
        return language === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
    }

    // Helper function to determine if we should use template
    function shouldUseTemplate(currentCode, newLanguage) {
        if (!currentCode) return true;

        // Check if the current code matches either language's characteristics
        const isCppCode = currentCode.includes('#include') || 
                         currentCode.includes('using namespace std') ||
                         currentCode.includes('int main()');

        const isCsharpCode = currentCode.includes('using System') || 
                            currentCode.includes('class Program') ||
                            currentCode.includes('static void Main');

        // If switching from C++ to C# or vice versa, use template
        return (newLanguage === 'cpp' && isCsharpCode) || 
               (newLanguage === 'csharp' && isCppCode);
    }

    // Helper function to get template for specific language
    function getTemplateForLanguage(language) {
        if (language === 'cpp') {
            return `#include <iostream>
using namespace std;

int main() {
    // Votre code ici
    return 0;
}`;
        } else {
            return `using System;

class Program {
    static void Main() {
        // Votre code ici
    }
}`;
        }
    }

    // Handle run button clicks
    const runButton = document.getElementById('runButton');
    const outputDiv = document.getElementById('output');
    if (runButton && outputDiv) {
        runButton.addEventListener('click', async function() {
            const code = editor.getValue().trim();
            if (!code) {
                outputDiv.innerHTML = '<div class="error">Le code ne peut pas être vide</div>';
                return;
            }

            runButton.disabled = true;
            outputDiv.innerHTML = '<div class="loading">Exécution du code...</div>';
            hasExecuted = true;  // Set execution flag

            try {
                // Get CSRF token from meta tag
                const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
                if (!csrfToken) {
                    throw new Error('CSRF token not found');
                }

                const response = await fetch('/activities/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify({
                        code,
                        language: languageSelect ? languageSelect.value : 'cpp'
                    })
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => null);
                    throw new Error(errorData?.error || `HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                outputDiv.innerHTML = data.error ? 
                    `<div class="error">${data.error}</div>` : 
                    `<pre>${data.output || 'Pas de sortie'}</pre>`;
            } catch (error) {
                console.error('Execution error:', error);
                outputDiv.innerHTML = `<div class="error">Erreur d'exécution: ${error.message}</div>`;
            } finally {
                runButton.disabled = false;
            }
        });
    }

    // Log successful initialization
    console.log('Editor initialized successfully');
});