// Templates
const cppTemplate = `#include <iostream>
#include <string>
#include <vector>

int main() {
    std::cout << "Hello World!" << std::endl;
    return 0;
}`;

const csharpTemplate = `using System;
using System.Collections.Generic;

class Program {
    static void Main(string[] args) {
        Console.WriteLine("Hello World!");
    }
}`;

let editor = null;

function initializeEditor(initialLanguage) {
    console.log('Initializing editor with language:', initialLanguage);
    const editorElement = document.getElementById('editor');

    if (!editorElement) {
        console.error('Editor element not found');
        return;
    }

    // Initialize CodeMirror
    editor = CodeMirror.fromTextArea(editorElement, {
        mode: initialLanguage === 'cpp' ? 'text/x-c++src' : 'text/x-csharp',
        theme: 'dracula',
        lineNumbers: true,
        matchBrackets: true,
        autoCloseBrackets: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: true,
        lineWrapping: true
    });

    // Set initial template
    const initialTemplate = initialLanguage === 'cpp' ? cppTemplate : csharpTemplate;
    console.log('Setting initial template for:', initialLanguage);
    editor.setValue(initialTemplate);

    // Force refresh to ensure proper rendering
    setTimeout(() => {
        editor.refresh();
    }, 100);

    return editor;
}

document.addEventListener('DOMContentLoaded', function() {
    const languageSelect = document.getElementById('languageSelect');
    const initialLanguage = languageSelect ? languageSelect.value : 'cpp';

    console.log('DOM loaded, initializing with language:', initialLanguage);
    editor = initializeEditor(initialLanguage);

    // Language switching handler
    if (languageSelect) {
        languageSelect.addEventListener('change', function(event) {
            const selectedLanguage = event.target.value;
            console.log('Language changed to:', selectedLanguage);

            if (editor) {
                const mode = selectedLanguage === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
                const template = selectedLanguage === 'cpp' ? cppTemplate : csharpTemplate;

                editor.setOption('mode', mode);
                editor.setValue(template);

                // Force refresh to ensure proper rendering
                setTimeout(() => {
                    editor.refresh();
                }, 100);

                console.log('Template switched for:', selectedLanguage);
            } else {
                console.error('Editor not initialized');
            }
        });
    }

    // Run button handler
    const runButton = document.getElementById('runButton');
    const outputDiv = document.getElementById('output');

    if (runButton && outputDiv) {
        runButton.addEventListener('click', async function() {
            const code = editor.getValue().trim();
            if (!code) {
                outputDiv.innerHTML = '<div class="error">Code cannot be empty</div>';
                return;
            }

            runButton.disabled = true;
            outputDiv.innerHTML = '<div class="loading">Running code...</div>';

            try {
                const response = await fetch('/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('input[name="csrf_token"]')?.value
                    },
                    body: JSON.stringify({ 
                        code, 
                        language: languageSelect ? languageSelect.value : 'cpp' 
                    })
                });

                const data = await response.json();
                outputDiv.innerHTML = data.error ? 
                    `<pre class="error">${data.error}</pre>` : 
                    `<pre>${data.output || 'No output'}</pre>`;
            } catch (error) {
                outputDiv.innerHTML = `<pre class="error">Execution error: ${error.message}</pre>`;
            } finally {
                runButton.disabled = false;
            }
        });
    }
});