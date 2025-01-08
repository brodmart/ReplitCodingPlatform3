document.addEventListener('DOMContentLoaded', function() {
    // Wait for InteractiveConsole to be available
    if (typeof InteractiveConsole === 'undefined') {
        console.error('InteractiveConsole not loaded. Make sure console.js is loaded first.');
        return;
    }

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
    const console = new InteractiveConsole({
        lang: document.documentElement.lang || 'fr'
    });

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
            if (!code) return;

            const language = languageSelect ? languageSelect.value : 'cpp';
            await console.executeCode(code, language);
        });
    }
});