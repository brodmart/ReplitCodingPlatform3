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

// Wait for DOM to be fully loaded before initializing
window.addEventListener('load', function() {
    console.log('Window loaded, initializing editor...');

    const editorElement = document.getElementById('editor');
    if (!editorElement) {
        console.error('Editor element not found');
        return;
    }

    // Get initial language
    const languageSelect = document.getElementById('languageSelect');
    const initialLanguage = languageSelect ? languageSelect.value : 'cpp';

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
        lineWrapping: true,
        value: initialLanguage === 'cpp' ? cppTemplate : csharpTemplate
    });

    // Set initial template
    const template = initialLanguage === 'cpp' ? cppTemplate : csharpTemplate;
    editor.setValue(template);

    // Handle language switching
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const selectedLanguage = this.value;
            const mode = selectedLanguage === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
            const template = selectedLanguage === 'cpp' ? cppTemplate : csharpTemplate;

            editor.setOption('mode', mode);
            editor.setValue(template);
            editor.refresh();
        });
    }

    // Handle run button
    const runButton = document.getElementById('runButton');
    const outputDiv = document.getElementById('output');

    if (runButton && outputDiv) {
        runButton.addEventListener('click', async function() {
            if (!editor) {
                outputDiv.innerHTML = '<div class="error">Editor not initialized</div>';
                return;
            }

            const code = editor.getValue().trim();
            const language = document.getElementById('languageSelect')?.value || 'cpp';

            if (!code) {
                outputDiv.innerHTML = '<div class="error">Le code ne peut pas être vide</div>';
                return;
            }

            runButton.disabled = true;
            outputDiv.innerHTML = '<div class="loading">Compiling and executing code...</div>';

            try {
                const response = await fetch('/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('input[name="csrf_token"]')?.value
                    },
                    body: JSON.stringify({ code, language })
                });

                const data = await response.json();

                if (data.error) {
                    outputDiv.innerHTML = `<pre class="error">${data.error}</pre>`;
                } else {
                    outputDiv.innerHTML = `<pre>${data.output || 'No output'}</pre>`;
                }
            } catch (error) {
                console.error('Execution error:', error);
                outputDiv.innerHTML = `<pre class="error">Execution error: ${error.message}</pre>`;
            } finally {
                runButton.disabled = false;
            }
        });
    }

    console.log('Editor initialized successfully');
});