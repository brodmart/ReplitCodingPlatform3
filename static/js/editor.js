
// Editor initialization
let editor = null;

document.addEventListener('DOMContentLoaded', function() {
    initializeEditor();
});

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
        lineWrapping: true,
        viewportMargin: Infinity,
        extraKeys: {
            "Tab": "indentMore",
            "Shift-Tab": "indentLess"
        }
    });

    // Default C++ template with more examples
    const cppTemplate = `#include <iostream>
#include <string>
#include <vector>
#include <algorithm>

using namespace std;

// Function to demonstrate vectors
void printVector(const vector<int>& vec) {
    for(int num : vec) {
        cout << num << " ";
    }
    cout << endl;
}

int main() {
    // Basic output
    cout << "Hello World!" << endl;
    
    // Working with vectors
    vector<int> numbers = {5, 2, 8, 1, 9};
    cout << "Original vector: ";
    printVector(numbers);
    
    // Sort the vector
    sort(numbers.begin(), numbers.end());
    cout << "Sorted vector: ";
    printVector(numbers);
    
    // String manipulation
    string name;
    cout << "Enter your name: ";
    getline(cin, name);
    cout << "Welcome, " << name << "!" << endl;
    
    return 0;
}`;

    // Default C# template with more examples
    const csharpTemplate = `using System;
using System.Collections.Generic;
using System.Linq;

class Program {
    // Function to demonstrate lists
    static void PrintList(List<int> list) {
        Console.WriteLine(string.Join(" ", list));
    }
    
    static void Main(string[] args) {
        // Basic output
        Console.WriteLine("Hello World!");
        
        // Working with lists
        List<int> numbers = new List<int> { 5, 2, 8, 1, 9 };
        Console.Write("Original list: ");
        PrintList(numbers);
        
        // Sort the list
        numbers.Sort();
        Console.Write("Sorted list: ");
        PrintList(numbers);
        
        // String manipulation
        Console.Write("Enter your name: ");
        string name = Console.ReadLine();
        Console.WriteLine($"Welcome, {name}!");
        
        // LINQ example
        var evenNumbers = numbers.Where(x => x % 2 == 0).ToList();
        Console.Write("Even numbers: ");
        PrintList(evenNumbers);
    }
}`;

    // Set initial template
    const languageSelect = document.getElementById('languageSelect');
    const currentLanguage = languageSelect ? languageSelect.value : 'cpp';
    if (editor) {
        editor.setValue(currentLanguage === 'cpp' ? cppTemplate : csharpTemplate);
        editor.refresh();
    }

    // Language switching
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const mode = this.value === 'cpp' ? 'text/x-c++src' : 'text/x-csharp';
            const template = this.value === 'cpp' ? cppTemplate : csharpTemplate;
            editor.setOption('mode', mode);
            editor.setValue(template);
            editor.refresh();
            console.log('Language changed to:', this.value);
        });
    }

    setupRunButton();
    editor.refresh();
}

function setupRunButton() {
    const runButton = document.getElementById('runButton');
    const outputDiv = document.getElementById('output');

    if (!runButton || !outputDiv) {
        console.error('Required elements not found');
        return;
    }

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

        outputDiv.innerHTML = '<div class="text-muted">Executing...</div>';

        try {
            const csrfTokenElement = document.querySelector('input[name="csrf_token"]');
            if (!csrfTokenElement) {
                throw new Error('CSRF token not found');
            }
            const csrfToken = csrfTokenElement.value;

            const response = await fetch('/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ code, language }),
                credentials: 'same-origin'
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Error executing code');

            outputDiv.innerHTML = data.error ? 
                `<pre class="error">${data.error}</pre>` : 
                `<pre>${data.output || 'No output'}</pre>`;
        } catch (error) {
            outputDiv.innerHTML = `<pre class="error">${error.message}</pre>`;
        }
    });
}
