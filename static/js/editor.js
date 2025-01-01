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

// Initialize Monaco Editor
require(['vs/editor/editor.main'], function() {
    const languageSelect = document.getElementById('languageSelect');
    const initialLanguage = languageSelect ? languageSelect.value : 'cpp';

    console.log('Initializing Monaco Editor with language:', initialLanguage);

    // Create editor instance
    editor = monaco.editor.create(document.getElementById('editor'), {
        value: initialLanguage === 'cpp' ? cppTemplate : csharpTemplate,
        language: initialLanguage === 'cpp' ? 'cpp' : 'csharp',
        theme: 'vs-dark',
        automaticLayout: true,
        minimap: {
            enabled: false
        },
        fontSize: 14,
        lineNumbers: 'on',
        roundedSelection: false,
        scrollBeyondLastLine: false,
        readOnly: false,
        cursorStyle: 'line'
    });

    // Language switching handler
    if (languageSelect) {
        languageSelect.addEventListener('change', function(event) {
            const selectedLanguage = event.target.value;
            console.log('Language changed to:', selectedLanguage);

            if (editor) {
                const template = selectedLanguage === 'cpp' ? cppTemplate : csharpTemplate;
                const model = monaco.editor.createModel(template, selectedLanguage === 'cpp' ? 'cpp' : 'csharp');
                editor.setModel(model);
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