// Web Console I/O Handler
console.debug('Initializing web console...');

let activeSession = null;
let outputBuffer = '';
let webSocket = null;

function initializeConsole() {
    console.debug('Setting up console handlers');
    activeSession = null;
    outputBuffer = '';
    setupWebSocket();
}

function setupWebSocket() {
    if (webSocket) {
        webSocket.close();
    }

    // Create WebSocket connection for real-time console I/O
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/console/ws`;
    webSocket = new WebSocket(wsUrl);

    webSocket.onopen = () => {
        console.debug('WebSocket connection established');
    };

    webSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'output') {
            updateConsoleDisplay({
                output: data.output,
                waitingForInput: data.waiting_for_input
            });
        }
    };

    webSocket.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    webSocket.onclose = () => {
        console.debug('WebSocket connection closed');
        // Attempt to reconnect after a delay
        setTimeout(setupWebSocket, 5000);
    };
}

async function sendInput(input) {
    console.debug('Sending input:', input);
    try {
        if (!activeSession) {
            console.error('No active session for input');
            return false;
        }

        if (webSocket && webSocket.readyState === WebSocket.OPEN) {
            webSocket.send(JSON.stringify({
                type: 'input',
                session_id: activeSession,
                input: input + '\n'
            }));
            return true;
        }

        // Fallback to HTTP if WebSocket is not available
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

        // Only use HTTP polling if WebSocket is not available
        if (!webSocket || webSocket.readyState !== WebSocket.OPEN) {
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

            // Send session ID to WebSocket if available
            if (webSocket && webSocket.readyState === WebSocket.OPEN) {
                webSocket.send(JSON.stringify({
                    type: 'session_start',
                    session_id: activeSession
                }));
            } else {
                startOutputPolling();
            }
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
        if (!activeSession || (webSocket && webSocket.readyState === WebSocket.OPEN)) {
            console.debug('Stopping output polling - no active session or using WebSocket');
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
    // Implementation depends on the web console UI
    console.debug('Console output updated:', output);

    // Emit custom event for UI to handle
    const event = new CustomEvent('console-output', { 
        detail: output 
    });
    window.dispatchEvent(event);
}

// Initialize console when script loads
initializeConsole();