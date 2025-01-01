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

    // Language switching with proper template loading
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        // Set initial template based on selected language
        const initialTemplate = languageSelect.value === 'cpp' ? cppTemplate : csharpTemplate;
        const initialMode = languageSelect.value === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
        editor.setOption('mode', initialMode);
        editor.setValue(initialTemplate);

        languageSelect.addEventListener('change', function() {
            const selectedLanguage = this.value;
            const template = selectedLanguage === 'cpp' ? cppTemplate : csharpTemplate;
            const mode = selectedLanguage === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
            editor.setOption('mode', mode);
            editor.setValue(template);
            editor.refresh();
            console.log('Language switched to:', selectedLanguage, 'with mode:', mode);
        });
    } else {
        // If no language select, default to C++ template
        editor.setValue(cppTemplate);
    }

    editor.refresh();

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
        console.log('Executing code with language:', language);

        if (!code.trim()) {
            outputDiv.innerHTML = '<div class="error">Le code ne peut pas être vide</div>';
            return;
        }

        // Show loading state
        runButton.disabled = true;
        outputDiv.innerHTML = '<div class="loading">Compiling and executing code...</div>';

        try {
            const response = await fetch('/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]')?.value
                },
                body: JSON.stringify({ 
                    code, 
                    language 
                })
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