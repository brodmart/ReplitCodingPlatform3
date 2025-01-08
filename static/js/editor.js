document.addEventListener('DOMContentLoaded', function() {
    const editorElement = document.getElementById('editor');
    const languageSelect = document.getElementById('languageSelect');

    if (!editorElement) {
        console.error('Editor element not found');
        return;
    }

    // Initialize CodeMirror with enhanced settings
    const editor = CodeMirror.fromTextArea(editorElement, {
        mode: 'text/x-c++src',
        theme: 'dracula',
        lineNumbers: true,
        autoCloseBrackets: true,
        matchBrackets: true,
        indentUnit: 4,
        tabSize: 4,
        lineWrapping: true,
        gutters: ["CodeMirror-linenumbers"],
        extraKeys: {
            "Ctrl-Space": "autocomplete",
            "F11": function(cm) {
                cm.setOption("fullScreen", !cm.getOption("fullScreen"));
            },
            "Esc": function(cm) {
                if (cm.getOption("fullScreen")) cm.setOption("fullScreen", false);
            }
        }
    });

    function getTemplateForLanguage(language) {
        if (language === 'cpp') {
            return `#include <iostream>
#include <string>
using namespace std;

int main() {
    // Your code here
    return 0;
}`;
        } else {
            return `using System;

namespace ProgrammingActivity
{
    class Program 
    {
        static void Main(string[] args)
        {
            // Your code here
        }
    }
}`;
        }
    }

    // Set initial template
    const initialLanguage = languageSelect ? languageSelect.value : 'cpp';
    editor.setValue(getTemplateForLanguage(initialLanguage));
    editor.refresh();

    // Language change handler
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const language = this.value;
            editor.setOption('mode', language === 'cpp' ? 'text/x-c++src' : 'text/x-csharp');
            editor.setValue(getTemplateForLanguage(language));
            editor.refresh();
        });
    }

    // Run button handler
    const runButton = document.getElementById('runButton');
    if (runButton) {
        runButton.addEventListener('click', async function() {
            const code = editor.getValue().trim();
            const outputDiv = document.getElementById('output');
            if (!code || !outputDiv) return;

            const csrfToken = document.querySelector('meta[name="csrf-token"]').content; //Using meta tag for CSRF token
            if (!csrfToken) {
                outputDiv.textContent = 'CSRF token not found. Please refresh the page.';
                return;
            }

            try {
                const response = await fetch('/activities/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify({
                        code: code,
                        language: languageSelect ? languageSelect.value : 'cpp'
                    })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    outputDiv.textContent = `Error: ${errorData.error || response.statusText}`;
                    return;
                }

                const data = await response.json();
                outputDiv.textContent = data.output || 'No output';
            } catch (error) {
                console.error('Execution error:', error);
                outputDiv.textContent = `Error: ${error.message}`;
            }
        });
    }
});