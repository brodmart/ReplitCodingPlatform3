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
        lineWrapping: true
    });

    // Set initial template
    const languageSelect = document.getElementById('languageSelect');
    const initialLanguage = languageSelect ? languageSelect.value : 'cpp';
    const initialTemplate = initialLanguage === 'cpp' ? cppTemplate : csharpTemplate;

    editor.setValue(initialTemplate);
    editor.refresh();
}

function setupLanguageSwitch() {
    const languageSelect = document.getElementById('languageSelect');
    if (!languageSelect) {
        console.error('Language select not found');
        return;
    }

    languageSelect.addEventListener('change', function() {
        const selectedLanguage = this.value;
        const mode = selectedLanguage === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
        const template = selectedLanguage === 'cpp' ? cppTemplate : csharpTemplate;

        editor.setOption('mode', mode);
        editor.setValue(template);
        editor.refresh();
        console.log('Language switched to:', selectedLanguage, 'with mode:', mode);
    });
}

function setupRunButton() {
    const runButton = document.getElementById('runButton');
    const outputDiv = document.getElementById('output');

    if (!runButton || !outputDiv) {
        console.error('Run button or output div not found');
        return;
    }

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

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing editor...');
    initializeEditor();
    setupLanguageSwitch();
    setupRunButton();
    console.log('Editor initialization complete');
});