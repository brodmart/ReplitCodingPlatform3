
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
    if (!editorElement) return;

    editor = CodeMirror.fromTextArea(editorElement, {
        mode: 'text/x-c++src',
        theme: 'dracula',
        lineNumbers: true,
        matchBrackets: true,
        autoCloseBrackets: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: true,
        lineWrapping: true
    });

    // Set initial template content
    const languageSelect = document.getElementById('languageSelect');
    const currentLanguage = languageSelect ? languageSelect.value : 'cpp';
    const initialTemplate = currentLanguage === 'cpp' ? cppTemplate : csharpTemplate;
    editor.setValue(initialTemplate);

    // Language switching
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const selectedLanguage = this.value;
            const template = selectedLanguage === 'cpp' ? cppTemplate : csharpTemplate;
            const mode = selectedLanguage === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
            editor.setOption('mode', mode);
            editor.setValue(template);
            editor.refresh();
        });
    }

    setupRunButton();
});

function setupRunButton() {
    const runButton = document.getElementById('runButton');
    const outputDiv = document.getElementById('output');
    
    if (!runButton || !outputDiv) return;

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

        try {
            const response = await fetch('/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content
                },
                body: JSON.stringify({ code, language })
            });

            const data = await response.json();
            outputDiv.innerHTML = data.error ? 
                `<pre class="error">${data.error}</pre>` : 
                `<pre>${data.output || 'No output'}</pre>`;
        } catch (error) {
            outputDiv.innerHTML = `<pre class="error">${error.message}</pre>`;
        }
    });
}
