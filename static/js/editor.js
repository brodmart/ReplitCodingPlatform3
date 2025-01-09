// Initialize everything when the DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const editorElement = document.getElementById('editor');
    const languageSelect = document.getElementById('languageSelect');
    const runButton = document.getElementById('runButton');
    const clearConsoleButton = document.getElementById('clearConsole');
    const consoleOutput = document.getElementById('consoleOutput');

    if (!editorElement || !consoleOutput) {
        console.error('Required elements not found');
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

    // Initialize Interactive Console
    let console = null;
    let isRunning = false;
    let runDebounceTimer = null;

    function initializeConsole() {
        if (!window.InteractiveConsole) {
            consoleOutput.innerHTML = '<div class="console-error">Error: Console initialization failed</div>';
            return null;
        }

        try {
            return new InteractiveConsole({
                lang: document.documentElement.lang || 'en'
            });
        } catch (error) {
            consoleOutput.innerHTML = `<div class="console-error">Error: ${error.message}</div>`;
            return null;
        }
    }

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

    // Set initial template and initialize console
    const initialLanguage = languageSelect ? languageSelect.value : 'cpp';
    editor.setValue(editor.getValue() || getTemplateForLanguage(initialLanguage));
    editor.refresh();
    console = initializeConsole();

    // Language change handler
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const language = this.value;
            editor.setOption('mode', language === 'cpp' ? 'text/x-c++src' : 'text/x-csharp');
            if (!editor.getValue().trim()) {
                editor.setValue(getTemplateForLanguage(language));
                editor.refresh();
            }
        });
    }

    // Run button handler with improved error handling and debouncing
    if (runButton) {
        runButton.addEventListener('click', async function() {
            if (isRunning) return;

            // Clear any pending execution
            if (runDebounceTimer) {
                clearTimeout(runDebounceTimer);
            }

            runDebounceTimer = setTimeout(async () => {
                const code = editor.getValue().trim();
                if (!code) {
                    consoleOutput.innerHTML = '<div class="console-error">Error: No code to execute</div>';
                    return;
                }

                if (!console) {
                    console = initializeConsole();
                    if (!console) return;
                }

                isRunning = true;
                runButton.disabled = true;
                runButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running...`;

                try {
                    const language = languageSelect ? languageSelect.value : 'cpp';
                    await console.executeCode(code, language);
                } catch (error) {
                    console.error('Error executing code:', error);
                    consoleOutput.innerHTML = `<div class="console-error">Error: ${error.message}</div>`;
                } finally {
                    isRunning = false;
                    runButton.disabled = false;
                    runButton.innerHTML = document.documentElement.lang === 'fr' ? 'Exécuter' : 'Run';
                }
            }, 250); // 250ms debounce
        });

        // Add keyboard shortcut for running code
        document.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !isRunning) {
                e.preventDefault();
                runButton.click();
            }
        });
    }

    // Clear console handler
    if (clearConsoleButton) {
        clearConsoleButton.addEventListener('click', async function() {
            if (console) {
                await console.endSession();
            }
            consoleOutput.innerHTML = '';
        });
    }
});