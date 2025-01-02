// Templates
const cppTemplate = `#include <iostream>
using namespace std;

int main() {
    cout << "Hello World!" << endl;
    return 0;
}`;

const csharpTemplate = `using System;

class Program {
    static void Main(string[] args) {
        Console.WriteLine("Hello World!");
    }
}`;

let editor = null;

document.addEventListener('DOMContentLoaded', function() {
    const editorElement = document.getElementById('editor');
    const languageSelect = document.getElementById('languageSelect');
    const outputDiv = document.getElementById('output');
    const runButton = document.getElementById('runButton');

    if (!editorElement || !languageSelect) {
        console.error('Required elements not found');
        return;
    }

    // Initialize CodeMirror
    editor = CodeMirror.fromTextArea(editorElement, {
        mode: 'text/x-c++src', // Default to C++
        theme: 'dracula',
        lineNumbers: true,
        matchBrackets: true,
        autoCloseBrackets: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: true,
        lineWrapping: true
    });

    // Set initial template based on selected language
    const initialLanguage = languageSelect.value;
    if (initialLanguage === 'cpp') {
        editor.setValue(cppTemplate);
        editor.setOption('mode', 'text/x-c++src');
    } else if (initialLanguage === 'csharp') {
        editor.setValue(csharpTemplate);
        editor.setOption('mode', 'text/x-csharp');
    }

    // Language switching handler
    languageSelect.addEventListener('change', function() {
        const selectedLanguage = this.value;
        console.log('Switching language to:', selectedLanguage);

        editor.setValue(selectedLanguage === 'cpp' ? cppTemplate : csharpTemplate);
        editor.setOption('mode', selectedLanguage === 'cpp' ? 'text/x-c++src' : 'text/x-csharp');
        editor.refresh();
    });

    // Run button handler
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

    // Force a refresh after initialization
    setTimeout(() => {
        editor.refresh();
        console.log('Editor initialized successfully');
    }, 100);
});