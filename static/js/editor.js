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

document.addEventListener('DOMContentLoaded', function() {
    const editorElement = document.getElementById('editor');
    const languageSelect = document.getElementById('languageSelect');

    if (!editorElement || !languageSelect) {
        console.error('Required elements not found');
        return;
    }

    // Initialize CodeMirror
    try {
        editor = CodeMirror.fromTextArea(editorElement, {
            mode: 'text/x-c++src', // Default to C++
            theme: 'dracula',
            lineNumbers: true,
            matchBrackets: true,
            autoCloseBrackets: true,
            indentUnit: 4,
            tabSize: 4,
            indentWithTabs: true,
            lineWrapping: true,
            value: cppTemplate
        });

        // Set initial content
        editor.setValue(cppTemplate);

        console.log('Editor initialized successfully');

        // Language switching handler
        languageSelect.addEventListener('change', function() {
            const selectedLanguage = this.value;
            console.log('Switching to language:', selectedLanguage);

            const mode = selectedLanguage === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
            const template = selectedLanguage === 'cpp' ? cppTemplate : csharpTemplate;

            editor.setOption('mode', mode);
            editor.setValue(template);
            editor.refresh();

            console.log('Template switched successfully');
        });

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
    } catch (error) {
        console.error('Failed to initialize editor:', error);
        if (editorElement) {
            editorElement.value = `Failed to initialize editor: ${error.message}`;
        }
    }
});