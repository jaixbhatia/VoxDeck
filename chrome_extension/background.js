// Listen for installation
chrome.runtime.onInstalled.addListener(() => {
    console.log('VoxDeck extension installed');
});

// Initialize extension state
chrome.runtime.onStartup.addListener(() => {
    console.log('VoxDeck extension started');
});

let recognition = null;
let isListening = false;

// Send message to content script to update display
async function updateDisplay(tabId, text) {
  try {
    // Inject content script if not already injected
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['content.js']
    }).catch(() => console.log('Content script already injected'));

    await chrome.tabs.sendMessage(tabId, {
      action: 'updateDisplay',
      text: text
    });
  } catch (error) {
    console.error('Error updating display:', error);
  }
}

function updateIcon(isRecording) {
  const path = isRecording ? {
    "16": "icons/mic-on-16.png",
    "48": "icons/mic-on-48.png",
    "128": "icons/mic-on-128.png"
  } : {
    "16": "icons/mic-off-16.png",
    "48": "icons/mic-off-48.png",
    "128": "icons/mic-off-128.png"
  };
  
  chrome.action.setIcon({ path });
}

async function initializeSpeechRecognition() {
  if (!recognition) {
    // Execute in the context of a tab to access webkitSpeechRecognition
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return;

    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        // Create and configure recognition in the tab context
        const recognition = new window.webkitSpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';
        return true;
      }
    });

    recognition = {};  // Placeholder to prevent re-initialization
    
    // Listen for recognition results from content script
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (message.type === 'transcription') {
        updateDisplay(tab.id, message.text);
      }
    });
  }
}

async function startListening() {
  await initializeSpeechRecognition();
  
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) {
    try {
      await chrome.tabs.sendMessage(tab.id, { action: 'startListening' });
      isListening = true;
      updateIcon(true);
      await updateDisplay(tab.id, 'Listening...');
    } catch (error) {
      console.error('Error starting listening:', error);
      isListening = false;
      updateIcon(false);
    }
  }
}

async function stopListening() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) {
    try {
      await chrome.tabs.sendMessage(tab.id, { action: 'stopListening' });
      isListening = false;
      updateIcon(false);
      await updateDisplay(tab.id, '');
    } catch (error) {
      console.error('Error stopping listening:', error);
    }
  }
}

// Toggle recording function
async function toggleRecording(tab) {
  if (!isListening) {
    try {
      // Inject content script if not already injected
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js']
      }).catch(() => console.log('Content script already injected'));

      // Request microphone access through content script
      const response = await chrome.tabs.sendMessage(tab.id, {
        action: 'requestMicrophoneAccess'
      });
      
      if (response.success) {
        await startListening();
      } else {
        throw new Error(response.error || 'Failed to get microphone access');
      }
    } catch (error) {
      console.error('Error accessing microphone:', error);
      await updateDisplay(tab.id, 'Please allow microphone access in Chrome settings');
    }
  } else {
    await stopListening();
  }
}

// Handle extension icon click
chrome.action.onClicked.addListener(async (tab) => {
  await toggleRecording(tab);
});

// Handle keyboard shortcut
chrome.commands.onCommand.addListener(async (command) => {
  if (command === 'toggle-recording') {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) {
      await toggleRecording(tab);
    }
  }
}); 