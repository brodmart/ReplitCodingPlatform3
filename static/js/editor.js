// Initialize everything when the DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const editorElement = document.getElementById('editor');
    const languageSelect = document.getElementById('languageSelect');
    const runButton = document.getElementById('runButton');

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
    string name;
    cout << "Enter your name: ";
    getline(cin, name);
    cout << "Hello, " << name << "!" << endl;
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
            Console.Write("Enter your name: ");
            string name = Console.ReadLine();
            Console.WriteLine($"Hello, {name}!");
        }
    }
}`;
        }
    }

    // Set initial template
    const initialLanguage = languageSelect ? languageSelect.value : 'cpp';
    editor.setValue(getTemplateForLanguage(initialLanguage));
    editor.refresh();

    // Initialize Interactive Console
    const consoleElements = {
        output: document.getElementById('consoleOutput'),
        input: document.getElementById('consoleInput')
    };

    let console;
    let isRunning = false;

    if (consoleElements.output && consoleElements.input) {
        console = new InteractiveConsole({
            lang: document.documentElement.lang || 'en'
        });
    }

    // Language change handler
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const language = this.value;
            editor.setOption('mode', language === 'cpp' ? 'text/x-c++src' : 'text/x-csharp');
            editor.setValue(getTemplateForLanguage(language));
            editor.refresh();
        });
    }

    // Run button handler with state management
    if (runButton && console) {
        runButton.addEventListener('click', async function() {
            if (isRunning) return; // Prevent multiple executions

            const code = editor.getValue().trim();
            if (!code) return;

            try {
                isRunning = true;
                runButton.disabled = true;
                runButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running...`;

                const language = languageSelect ? languageSelect.value : 'cpp';
                await console.executeCode(code, language);
            } catch (error) {
                console.appendToConsole(`Error: ${error.message}\n`, 'error');
            } finally {
                isRunning = false;
                runButton.disabled = false;
                runButton.innerHTML = languageSelect.value === 'fr' ? 'Exécuter' : 'Run';
            }
        });

        // Add keyboard shortcut for running code
        document.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !isRunning) {
                e.preventDefault();
                runButton.click();
            }
        });
    }
});