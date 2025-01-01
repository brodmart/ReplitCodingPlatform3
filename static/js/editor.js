
// Editor initialization
let editor = null;

document.addEventListener('DOMContentLoaded', function() {
    initializeEditor();
});

function initializeEditor() {
    const editorElement = document.getElementById('editor');
    if (!editorElement) {
        console.error('Editor element not found');
        return;
    }

    // Initialize CodeMirror
    editor = CodeMirror.fromTextArea(editorElement, {
        mode: 'text/x-c++src',
        theme: 'dracula',
        lineNumbers: true,
        matchBrackets: true,
        autoCloseBrackets: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: true,
        lineWrapping: true,
        viewportMargin: Infinity,
        extraKeys: {
            "Tab": "indentMore",
            "Shift-Tab": "indentLess"
        }
    });

    // Templates
    const templates = {
        'cpp': `#include <iostream>
#include <string>
#include <vector>

int main() {
    std::cout << "Hello World!" << std::endl;
    return 0;
}`,
        'csharp': `using System;
using System.Collections.Generic;

class Program {
    static void Main(string[] args) {
        Console.WriteLine("Hello World!");
    }
}`
    };

    // Set initial template based on selected language
    const languageSelect = document.getElementById('languageSelect');
    const currentLanguage = languageSelect ? languageSelect.value : 'cpp';
    editor.setValue(templates[currentLanguage]);

    // Language switching
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const mode = this.value === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
            editor.setOption('mode', mode);
            editor.setValue(templates[this.value]);
            editor.refresh();
        });
    }

    setupRunButton();
    editor.refresh();
}

function setupRunButton() {
    const runButton = document.getElementById('runButton');
    const outputDiv = document.getElementById('output');

    if (!runButton || !outputDiv) {
        console.error('Required elements not found');
        return;
    }

    runButton.addEventListener('click', async function() {
        if (!editor) {
            outputDiv.innerHTML = '<div class="error">Editor not initialized</div>';
            return;
        }

        const code = editor.getValue();
        const language = document.getElementById('languageSelect')?.value || 'cpp';

        if (!code.trim()) {
            outputDiv.innerHTML = '<div class="error">Code cannot be empty</div>';
            return;
        }

        outputDiv.innerHTML = '<div class="text-muted">Executing...</div>';

        try {
            const csrfTokenElement = document.querySelector('input[name="csrf_token"]');
            if (!csrfTokenElement) {
                throw new Error('CSRF token not found');
            }
            const csrfToken = csrfTokenElement.value;

            const response = await fetch('/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ code, language }),
                credentials: 'same-origin'
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Error executing code');

            outputDiv.innerHTML = data.error ? 
                `<pre class="error">${data.error}</pre>` : 
                `<pre>${data.output || 'No output'}</pre>`;
        } catch (error) {
            outputDiv.innerHTML = `<pre class="error">${error.message}</pre>`;
        }
    });
}
