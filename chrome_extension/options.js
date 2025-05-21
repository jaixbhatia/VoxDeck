document.addEventListener('DOMContentLoaded', async function() {
    const micStatus = document.getElementById('micStatus');
    const requestButton = document.getElementById('requestPermission');

    // Function to update UI based on permission state
    function updatePermissionStatus(state) {
        if (state === 'granted') {
            micStatus.textContent = '✅ Microphone access is enabled';
            micStatus.className = 'status success';
            requestButton.style.display = 'none';
            // Store the permission state
            chrome.storage.local.set({ micPermissionGranted: true });
        } else if (state === 'denied') {
            micStatus.textContent = '❌ Microphone access was denied. Please enable it in your browser settings.';
            micStatus.className = 'status error';
            requestButton.style.display = 'block';
        } else {
            micStatus.textContent = 'ℹ️ Microphone permission not yet granted';
            micStatus.className = 'status';
            requestButton.style.display = 'block';
        }
    }

    // Check initial permission state
    try {
        const result = await navigator.permissions.query({ name: 'microphone' });
        updatePermissionStatus(result.state);
        
        // Listen for permission changes
        result.onchange = function() {
            updatePermissionStatus(this.state);
        };
    } catch (error) {
        console.error('Error checking permission:', error);
        micStatus.textContent = 'Error checking microphone permission';
        micStatus.className = 'status error';
    }

    // Handle permission request button click
    requestButton.addEventListener('click', async () => {
        try {
            // Request microphone access
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            updatePermissionStatus('granted');
            // Stop the stream since we don't need it anymore
            stream.getTracks().forEach(track => track.stop());
        } catch (error) {
            console.error('Error requesting microphone access:', error);
            updatePermissionStatus('denied');
        }
    });
}); 