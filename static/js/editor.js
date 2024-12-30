let editor;

require.config({
    paths: {
        'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs'
    }
});

require(['vs/editor/editor.main'], function() {
    editor = monaco.editor.create(document.getElementById('editor'), {
        value: getDefaultCode('cpp'),
        language: 'cpp',
        theme: 'vs-dark',
        minimap: {
            enabled: false
        },
        automaticLayout: true,
        fontSize: 14,
        scrollBeyondLastLine: false,
        renderWhitespace: 'selection',
        padding: {
            top: 10,
            bottom: 10
        }
    });

    // Language change handler
    document.getElementById('languageSelect').addEventListener('change', function(e) {
        const language = e.target.value;
        monaco.editor.setModelLanguage(editor.getModel(), language);
        editor.setValue(getDefaultCode(language));
    });

    // Run button handler
    document.getElementById('runButton').addEventListener('click', executeCode);
});

function getDefaultCode(language) {
    if (language === 'cpp') {
        return `#include <iostream>

int main() {
    std::cout << "Hello, World!" << std::endl;
    return 0;
}`;
    } else if (language === 'csharp') {
        return `using System;

class Program {
    static void Main() {
        Console.WriteLine("Hello, World!");
    }
}`;
    }
}

async function executeCode() {
    const runButton = document.getElementById('runButton');
    const output = document.getElementById('output');
    const language = document.getElementById('languageSelect').value;
    
    try {
        runButton.disabled = true;
        runButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...';
        
        const response = await fetch('/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                code: editor.getValue(),
                language: language
            })
        });
        
        const result = await response.json();
        
        if (result.error) {
            output.innerHTML = `<span style="color: var(--bs-danger)">Error:\n${result.error}</span>`;
        } else {
            output.innerHTML = result.output || 'Program executed successfully with no output.';
        }
    } catch (error) {
        output.innerHTML = `<span style="color: var(--bs-danger)">Error: ${error.message}</span>`;
    } finally {
        runButton.disabled = false;
        runButton.innerHTML = '<i class="bi bi-play-fill"></i> Run';
    }
}

// Handle window resize
window.addEventListener('resize', function() {
    if (editor) {
        editor.layout();
    }
});
