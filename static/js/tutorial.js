document.addEventListener('DOMContentLoaded', function() {
    // Initialize CodeMirror
    const editor = CodeMirror.fromTextArea(document.getElementById('editor'), {
        mode: 'text/x-c++src',
        theme: 'dracula',
        lineNumbers: true,
        autoCloseBrackets: true,
        matchBrackets: true,
        indentUnit: 4,
        tabSize: 4,
        lineWrapping: true,
        gutters: ["CodeMirror-linenumbers", "CodeMirror-lint-markers"],
        lint: true,
        extraKeys: {
            "Ctrl-Space": "autocomplete",
            "Tab": "indentMore",
            "Shift-Tab": "indentLess"
        }
    });

    // Tutorial state
    let currentStep = parseInt(document.querySelector('.step-dot.active').textContent) - 1;
    const totalSteps = document.querySelectorAll('.step-dot').length;
    let stepValidated = false;

    // Navigation buttons
    const prevButton = document.getElementById('prevStep');
    const nextButton = document.getElementById('nextStep');

    // Validation message elements
    const validationMessage = document.querySelector('.validation-message');
    const messageText = document.querySelector('.message-text');

    // Step validation patterns
    const stepValidations = {
        // Example validation patterns - these would be populated from the server
        0: {
            required: ['#include <iostream>', 'using namespace std'],
            forbidden: ['using namespace std::cout'],
            pattern: /int\s+main\s*\(\s*\)\s*{.*}/s
        },
        1: {
            required: ['cout', '<<', 'endl'],
            pattern: /cout\s*<<\s*["'].*["']\s*<<\s*endl\s*;/
        }
        // Add more validation patterns for each step
    };

    // Validate current step
    function validateStep() {
        const code = editor.getValue();
        const validation = stepValidations[currentStep];
        
        if (!validation) {
            return true; // No validation rules for this step
        }

        let isValid = true;
        let errorMessage = '';

        // Check required elements
        if (validation.required) {
            for (const req of validation.required) {
                if (!code.includes(req)) {
                    isValid = false;
                    errorMessage = `Missing required element: ${req}`;
                    break;
                }
            }
        }

        // Check forbidden elements
        if (isValid && validation.forbidden) {
            for (const forb of validation.forbidden) {
                if (code.includes(forb)) {
                    isValid = false;
                    errorMessage = `Found forbidden element: ${forb}`;
                    break;
                }
            }
        }

        // Check pattern
        if (isValid && validation.pattern) {
            if (!validation.pattern.test(code)) {
                isValid = false;
                errorMessage = 'Code structure does not match the required pattern';
            }
        }

        // Update UI
        validationMessage.className = 'validation-message ' + (isValid ? 'success' : 'error');
        messageText.textContent = isValid ? 'Great job! You can proceed to the next step.' : errorMessage;
        validationMessage.style.display = 'block';

        return isValid;
    }

    // Add syntax highlighting for specific constructs
    function highlightSyntax() {
        editor.operation(() => {
            // Clear existing marks
            editor.getAllMarks().forEach(mark => mark.clear());

            const code = editor.getValue();
            const lines = code.split('\n');

            lines.forEach((line, i) => {
                // Highlight includes
                if (/#include/.test(line)) {
                    editor.markText(
                        {line: i, ch: line.indexOf('#')},
                        {line: i, ch: line.length},
                        {className: 'syntax-include'}
                    );
                }

                // Highlight function declarations
                const functionMatch = line.match(/\b\w+\s+\w+\s*\([^)]*\)/);
                if (functionMatch) {
                    const start = line.indexOf(functionMatch[0]);
                    editor.markText(
                        {line: i, ch: start},
                        {line: i, ch: start + functionMatch[0].length},
                        {className: 'syntax-function'}
                    );
                }

                // Highlight string literals
                const stringMatches = line.match(/"[^"]*"/g);
                if (stringMatches) {
                    stringMatches.forEach(match => {
                        const start = line.indexOf(match);
                        editor.markText(
                            {line: i, ch: start},
                            {line: i, ch: start + match.length},
                            {className: 'syntax-string'}
                        );
                    });
                }
            });
        });
    }

    // Update progress indicators
    function updateProgress() {
        const progress = ((currentStep + 1) / totalSteps) * 100;
        document.querySelector('.progress-fill').style.width = `${progress}%`;

        // Update step dots
        document.querySelectorAll('.step-dot').forEach((dot, index) => {
            dot.classList.remove('active', 'completed');
            if (index < currentStep) {
                dot.classList.add('completed');
            } else if (index === currentStep) {
                dot.classList.add('active');
            }
        });

        // Update navigation buttons
        prevButton.disabled = currentStep === 0;
        nextButton.textContent = currentStep === totalSteps - 1 ? 'Complete' : 'Next';
        nextButton.innerHTML = currentStep === totalSteps - 1 ? 
            'Complete <i class="bi bi-check-circle"></i>' : 
            'Next <i class="bi bi-arrow-right"></i>';
    }

    // Navigation event handlers
    prevButton.addEventListener('click', () => {
        if (currentStep > 0) {
            currentStep--;
            updateProgress();
            // Load previous step content from server
            loadStepContent(currentStep);
        }
    });

    nextButton.addEventListener('click', () => {
        if (validateStep()) {
            if (currentStep < totalSteps - 1) {
                currentStep++;
                updateProgress();
                // Load next step content from server
                loadStepContent(currentStep);
            } else {
                // Tutorial completed
                completeTutorial();
            }
        }
    });

    // Load step content from server
    async function loadStepContent(stepIndex) {
        try {
            const response = await fetch(`/tutorial/step/${stepIndex}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
                }
            });

            if (!response.ok) {
                throw new Error('Failed to load step content');
            }

            const data = await response.json();
            
            // Update instruction content
            document.querySelector('.instruction-header h5').textContent = data.title;
            document.querySelector('.tutorial-instruction p').textContent = data.description;
            
            // Update code hint if present
            const hintElement = document.querySelector('.code-hint');
            if (data.hint) {
                hintElement.style.display = 'block';
                hintElement.textContent = data.hint;
            } else {
                hintElement.style.display = 'none';
            }

            // Update editor content
            editor.setValue(data.starter_code || '');
            
            // Clear validation message
            validationMessage.style.display = 'none';
            
            // Refresh editor
            editor.refresh();
            
        } catch (error) {
            console.error('Error loading step content:', error);
            alert('Failed to load step content. Please try again.');
        }
    }

    // Complete tutorial
    function completeTutorial() {
        // Show completion modal
        const modal = document.createElement('div');
        modal.className = 'modal fade show';
        modal.style.display = 'block';
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content bg-dark text-light">
                    <div class="modal-header">
                        <h5 class="modal-title">Congratulations!</h5>
                    </div>
                    <div class="modal-body text-center">
                        <div class="mb-4">
                            <i class="bi bi-trophy text-warning" style="font-size: 3rem;"></i>
                        </div>
                        <h4>Tutorial Completed!</h4>
                        <p>You've successfully completed all the steps. Great job!</p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-primary" onclick="window.location.href='/tutorials'">
                            Return to Tutorials
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Initialize syntax highlighting
    editor.on('change', highlightSyntax);
    highlightSyntax();

    // Add custom styles for syntax highlighting
    const style = document.createElement('style');
    style.textContent = `
        .syntax-include {
            color: #ff79c6;
            font-weight: bold;
        }
        .syntax-function {
            color: #50fa7b;
        }
        .syntax-string {
            color: #f1fa8c;
        }
        .syntax-keyword {
            color: #ff79c6;
            font-weight: bold;
        }
        .syntax-type {
            color: #8be9fd;
            font-style: italic;
        }
        .syntax-comment {
            color: #6272a4;
            font-style: italic;
        }
    `;
    document.head.appendChild(style);

    // Initialize the first step
    updateProgress();
});
