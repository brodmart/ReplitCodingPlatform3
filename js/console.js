// Web Console I/O Handler
console.debug('Initializing web console...');

let activeSession = null;
let outputBuffer = '';

function initializeConsole() {
    console.debug('Setting up console handlers');
    activeSession = null;
    outputBuffer = '';
}

async function sendInput(input) {
    console.debug('Sending input:', input);
    try {
        if (!activeSession) {
            console.error('No active session for input');
            return false;
        }
        const response = await fetch('/console/send_input', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: activeSession,
                input: input + '\n'
            })
        });
        const result = await response.json();
        console.debug('Input result:', result);
        return result.success;
    } catch (error) {
        console.error('Error sending input:', error);
        return false;
    }
}

async function receiveOutput() {
    try {
        if (!activeSession) {
            console.error('No active session for output');
            return null;
        }
        const response = await fetch(`/console/get_output?session_id=${activeSession}`);
        const result = await response.json();
        console.debug('Received output:', result);

        if (result.success) {
            outputBuffer += result.output;
            return {
                output: result.output,
                waitingForInput: result.waiting_for_input
            };
        }
        return null;
    } catch (error) {
        console.error('Error receiving output:', error);
        return null;
    }
}

async function compileAndRun(code, language) {
    console.debug(`Compiling ${language} code:`, code);
    try {
        const response = await fetch('/compile', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ code, language })
        });
        const result = await response.json();
        console.debug('Compilation result:', result);

        if (result.success && result.interactive) {
            activeSession = result.session_id;
            console.debug('Interactive session started:', activeSession);
            startOutputPolling();
        }
        return result;
    } catch (error) {
        console.error('Compilation error:', error);
        return {
            success: false,
            error: 'Failed to compile: ' + error.message
        };
    }
}

function startOutputPolling() {
    console.debug('Starting output polling');
    const pollInterval = setInterval(async () => {
        if (!activeSession) {
            console.debug('Stopping output polling - no active session');
            clearInterval(pollInterval);
            return;
        }

        const output = await receiveOutput();
        if (output) {
            updateConsoleDisplay(output);
        }
    }, 100);
}

function updateConsoleDisplay(output) {
    // This function should be implemented by the web console UI
    console.debug('Console output updated:', output);
}

// Initialize console when script loads
initializeConsole();