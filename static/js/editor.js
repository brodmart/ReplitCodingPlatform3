// Initialize CodeMirror editor with default settings
document.addEventListener('DOMContentLoaded', function() {
    const editorElement = document.getElementById('editor');
    if (!editorElement) {
        console.error('Editor element not found');
        return;
    }

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

    // Default templates
    const templates = {
        cpp: `#include <iostream>
using namespace std;

int main() {
    cout << "Hello World!" << endl;
    return 0;
}`,
        csharp: `using System;

class Program {
    static void Main(string[] args) {
        Console.WriteLine("Hello World!");
    }
}`
    };

    // Set initial template and refresh editor
    const initialLanguage = document.getElementById('languageSelect')?.value || 'cpp';
    editor.setValue(templates[initialLanguage]);
    editor.refresh();

    // Handle language changes
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const language = this.value;
            console.log('Switching language to:', language);
            editor.setOption('mode', language === 'cpp' ? 'text/x-c++src' : 'text/x-csharp');
            editor.setValue(templates[language]);
            editor.refresh();
        });
    }

    // Handle run button clicks
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
                        language: languageSelect.value
                    })
                });

                const data = await response.json();
                outputDiv.innerHTML = data.error ? 
                    `<div class="error">${data.error}</div>` : 
                    `<pre>${data.output || 'No output'}</pre>`;
            } catch (error) {
                outputDiv.innerHTML = `<div class="error">Execution error: ${error.message}</div>`;
            } finally {
                runButton.disabled = false;
            }
        });
    }

    // Log successful initialization
    console.log('Editor initialized successfully');
});