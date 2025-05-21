document.addEventListener('DOMContentLoaded', async function () {
    const startButton = document.getElementById('startButton');
    const transcript = document.getElementById('transcript');
    let recognition = null;

    // Check if we have microphone permission
    try {
        const result = await navigator.permissions.query({ name: 'microphone' });
        if (result.state === 'denied') {
            transcript.textContent = 'Microphone access is required. Please click the extension icon and select "Options" to enable it.';
            startButton.disabled = true;
            return;
        } else if (result.state === 'prompt') {
            // Open options page to request permission
            chrome.runtime.openOptionsPage();
            window.close();
            return;
        }
    } catch (error) {
        console.error('Error checking permission:', error);
    }

    function initializeSpeechRecognition() {
        if (!recognition) {
            recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = 'en-US';

            recognition.onresult = function (event) {
                let text = '';
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    text += event.results[i][0].transcript;
                }
                transcript.textContent = text;
            };

            recognition.onerror = function (event) {
                console.error('Speech recognition error:', event.error);
                transcript.textContent = 'Error: ' + event.error;
                startButton.textContent = 'Start Recording';
            };

            recognition.onend = function () {
                startButton.textContent = 'Start Recording';
            };
        }
    }

    startButton.addEventListener('click', function () {
        if (!recognition) {
            initializeSpeechRecognition();
        }

        if (startButton.textContent === 'Start Recording') {
            recognition.start();
            startButton.textContent = 'Stop Recording';
        } else {
            recognition.stop();
            startButton.textContent = 'Start Recording';
        }
    });
});
  