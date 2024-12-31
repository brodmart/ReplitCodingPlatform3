
let editor = null;

require(['vs/editor/editor.main'], function() {
    const editorElement = document.getElementById('editor');
    if (!editorElement) return;

    const languageSelect = document.getElementById('languageSelect');
    const language = languageSelect ? languageSelect.value : 'cpp';
    
    editor = monaco.editor.create(editorElement, {
        value: getDefaultCode(language),
        language: language,
        theme: 'vs-dark',
        minimap: { enabled: false },
        automaticLayout: true,
        fontSize: 14
    });

    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            const newLanguage = languageSelect.value;
            monaco.editor.setModelLanguage(editor.getModel(), newLanguage);
            editor.setValue(getDefaultCode(newLanguage));
        });
    }
});

function getDefaultCode(language) {
    const templates = {
        cpp: '#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << "Hello World!" << endl;\n    return 0;\n}',
        python: 'print("Hello World!")',
        javascript: 'console.log("Hello World!");'
    };
    return templates[language] || templates.cpp;
}

async function executeCode() {
    if (!editor) {
        console.error('Editor not initialized');
        return;
    }

    const output = document.getElementById('output');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const languageSelect = document.getElementById('languageSelect');
    
    if (!csrfToken) {
        if (output) output.innerHTML = '<pre class="error">Erreur: CSRF token manquant</pre>';
        return;
    }

    try {
        const response = await fetch('/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                code: editor.getValue(),
                language: languageSelect ? languageSelect.value : 'cpp'
            })
        });

        const result = await response.json();
        if (output) {
            output.innerHTML = `<pre class="${result.success ? 'success' : 'error'}">${result.output || result.error}</pre>`;
        }
    } catch (error) {
        if (output) {
            output.innerHTML = `<pre class="error">Erreur d'exécution: ${error.message}</pre>`;
        }
    }
}
