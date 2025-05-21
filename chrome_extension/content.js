// Create a floating display for voice input
const createVoiceDisplay = () => {
  const display = document.createElement('div');
  display.id = 'voxdeck-voice-display';
  display.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 15px;
    background: rgba(0, 0, 0, 0.8);
    color: white;
    border-radius: 8px;
    font-family: Arial, sans-serif;
    z-index: 10000;
    min-width: 200px;
    display: none;
  `;
  document.body.appendChild(display);
  return display;
};

// Initialize voice recognition
const initVoiceRecognition = () => {
  const display = createVoiceDisplay();
  const recognition = new webkitSpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onstart = () => {
    display.style.display = 'block';
    display.textContent = 'Listening...';
  };

  recognition.onresult = (event) => {
    let finalTranscript = '';
    let interimTranscript = '';

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript += transcript;
      } else {
        interimTranscript += transcript;
      }
    }

    display.textContent = finalTranscript || interimTranscript || 'Listening...';
  };

  recognition.onerror = (event) => {
    display.textContent = `Error: ${event.error}`;
    console.error('Speech recognition error:', event.error);
  };

  recognition.onend = () => {
    // Automatically restart recognition
    recognition.start();
  };

  // Start recognition
  try {
    recognition.start();
  } catch (error) {
    console.error('Error starting speech recognition:', error);
  }
};

// Common styles
const THEME = {
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
  primary: '#1a1a1a',
  text: '#ffffff',
  accent: '#4285f4',
  danger: '#ff4444',
  success: '#4CAF50',
  fontSize: '16px',
  borderRadius: '12px',
  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)',
};

// Global variables
let scene, camera, renderer, analyser, dataArray, visualizer;
let isListening = false;
let restartTimeout = null;
const RESTART_DELAY = 300;
let recognition = null;
let audioContext = null;
let audioSource = null;

// Initialize audio context and analyzer
async function initAudio() {
    try {
        // Create audio context
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048; // Keep high FFT for good resolution
        analyser.smoothingTimeConstant = 0.75; // Reduced smoothing for more responsiveness
        dataArray = new Uint8Array(analyser.frequencyBinCount);

        // Get microphone stream
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioSource = audioContext.createMediaStreamSource(stream);
        audioSource.connect(analyser);
        
        return true;
    } catch (error) {
        console.error('Error initializing audio:', error);
        return false;
    }
}

// Initialize Three.js visualization
function initThreeJS(container) {
    try {
        scene = new THREE.Scene();
        
        // Set initial aspect ratio based on container dimensions
        const aspect = container.clientWidth / container.clientHeight;
        camera = new THREE.PerspectiveCamera(75, aspect, 0.1, 1000);
        camera.position.z = 15;
        
        renderer = new THREE.WebGLRenderer({ 
            alpha: true,
            antialias: true 
        });
        
        // Ensure renderer fills container
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.setClearColor(0x000000, 0);
        
        // Clear any existing canvas
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
        container.appendChild(renderer.domElement);

        // Ensure canvas fills container
        renderer.domElement.style.cssText = `
            width: 100% !important;
            height: 100% !important;
            display: block;
        `;

        // Create sphere with more vertices for better deformation
        const sphereGeometry = new THREE.SphereGeometry(5, 64, 64);
        
        // Create material with custom shader
        const material = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 },
                pulseIntensity: { value: 0.0 },
                baseColor: { value: new THREE.Color(0x3498db) }
            },
            vertexShader: `
                uniform float time;
                uniform float pulseIntensity;
                varying vec3 vNormal;
                varying float vDisplacement;

                void main() {
                    vNormal = normal;
                    vec3 newPosition = position;
                    
                    float displacement = sin(position.x * 10.0 + time) * 
                                       sin(position.y * 10.0 + time) * 
                                       sin(position.z * 10.0 + time) * pulseIntensity;
                    
                    vDisplacement = displacement;
                    newPosition += normal * displacement;
                    
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
                }
            `,
            fragmentShader: `
                uniform vec3 baseColor;
                varying vec3 vNormal;
                varying float vDisplacement;

                void main() {
                    vec3 light = normalize(vec3(1.0, 1.0, 1.0));
                    float intensity = dot(vNormal, light) * 0.5 + 0.5;
                    vec3 color = mix(baseColor, vec3(1.0), vDisplacement * 2.0 + 0.5);
                    gl_FragColor = vec4(color * intensity, 0.8);
                }
            `,
            transparent: true,
            side: THREE.DoubleSide
        });

        visualizer = new THREE.Mesh(sphereGeometry, material);
        scene.add(visualizer);

        // Add lights
        const light = new THREE.DirectionalLight(0xffffff, 1);
        light.position.set(5, 5, 5);
        scene.add(light);

        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        scene.add(ambientLight);

        // Update camera and renderer on container resize
        const resizeObserver = new ResizeObserver(() => {
            if (container.clientWidth > 0 && container.clientHeight > 0) {
                camera.aspect = container.clientWidth / container.clientHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(container.clientWidth, container.clientHeight);
            }
        });
        resizeObserver.observe(container);

        animate();
        return true;
    } catch (error) {
        console.error('Error initializing Three.js:', error);
        return false;
    }
}

function animate() {
    requestAnimationFrame(animate);
    
    if (analyser && isListening && visualizer?.material.uniforms) {
        try {
            analyser.getByteFrequencyData(dataArray);
            
            // Update time uniform
            visualizer.material.uniforms.time.value += 0.03;

            // Process audio data with improved frequency ranges
            let bassSum = 0;
            let midSum = 0;
            let trebleSum = 0;
            
            // Improved frequency range distribution
            const bassRange = Math.floor(dataArray.length * 0.1);  // 10% for bass
            const midRange = Math.floor(dataArray.length * 0.4);   // 40% for mids
            
            for (let i = 0; i < dataArray.length; i++) {
                const value = dataArray[i] / 255; // Normalize to 0-1
                if (i < bassRange) {
                    bassSum += value;
                } else if (i < midRange) {
                    midSum += value;
                } else {
                    trebleSum += value;
                }
            }

            // More responsive averages
            const bassAvg = Math.pow(bassSum / bassRange, 1.2) * 1.2; // Increased sensitivity
            const midAvg = (midSum / (midRange - bassRange)) * 0.8;   // Increased sensitivity
            const trebleAvg = (trebleSum / (dataArray.length - midRange)) * 0.7; // Increased sensitivity

            // More responsive pulse effect
            const targetPulse = Math.pow(bassAvg, 1.2) * 3.0 + midAvg * 1.2;
            const currentPulse = visualizer.material.uniforms.pulseIntensity.value;
            visualizer.material.uniforms.pulseIntensity.value += (targetPulse - currentPulse) * 0.15; // Faster transition
            
            // More dramatic color changes
            const hue = 0.6 + (bassAvg * 0.15 + midAvg * 0.2 + trebleAvg * 0.3) * 0.5;
            const saturation = 0.7 + (bassAvg * 0.3);
            const lightness = 0.5 + (midAvg * 0.25 + trebleAvg * 0.15);
            
            const color = new THREE.Color();
            color.setHSL(hue, saturation, lightness);
            visualizer.material.uniforms.baseColor.value = color;

            // More responsive rotation
            const targetRotationSpeed = 0.001 + (bassAvg * 0.015 + midAvg * 0.008);
            visualizer.rotation.x += targetRotationSpeed;
            visualizer.rotation.y += targetRotationSpeed * 1.2;
            
            // More responsive scaling
            const targetScale = 1 + (bassAvg * 0.3 + midAvg * 0.15);
            const currentScale = visualizer.scale.x;
            const newScale = currentScale + (targetScale - currentScale) * 0.15;
            visualizer.scale.set(newScale, newScale, newScale);
        } catch (error) {
            console.error('Error in animation:', error);
        }
    }

    if (renderer && scene && camera) {
        renderer.render(scene, camera);
    }
}

// Initialize speech recognition
async function initializeRecognition() {
    try {
        if (recognition) {
            recognition.stop();
            recognition = null;
        }

        // Initialize audio context and analyzer first
        const audioInitialized = await initAudio();
        if (!audioInitialized) {
            throw new Error('Failed to initialize audio');
        }

        recognition = new webkitSpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;

        recognition.onstart = () => {
            isListening = true;
            updateRecordButtonState(true);
        };

        recognition.onend = () => {
            isListening = false;
            updateRecordButtonState(false);
            
            if (document.querySelector('#voxdeck-record-button.recording')) {
                clearTimeout(restartTimeout);
                restartTimeout = setTimeout(() => {
                    if (document.querySelector('#voxdeck-record-button.recording')) {
                        startRecognition();
                    }
                }, RESTART_DELAY);
            }
        };

        recognition.onerror = (event) => {
            console.error('Recognition error:', event.error);
            isListening = false;
            updateRecordButtonState(false);
        };

        recognition.onresult = (event) => {
            let finalTranscript = '';
            let interimTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript;
                } else {
                    interimTranscript += transcript;
                }
            }

            if (finalTranscript || interimTranscript) {
                appendTranscript(finalTranscript, interimTranscript);
            }
        };

        return true;
    } catch (error) {
        console.error('Error initializing recognition:', error);
        return false;
    }
}

// Create or update the display container
function createOrUpdateDisplay() {
    const existingDisplay = document.getElementById('voxdeck-container');
    if (existingDisplay) {
        return existingDisplay;
    }

    const container = document.createElement('div');
    container.id = 'voxdeck-container';
    container.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 300px;
        background: ${THEME.primary};
        border-radius: ${THEME.borderRadius};
        box-shadow: ${THEME.boxShadow};
        font-family: ${THEME.fontFamily};
        color: ${THEME.text};
        z-index: 10000;
        overflow: hidden;
        min-width: 250px;
        min-height: 200px;
    `;

    // Create header
    const header = document.createElement('div');
    header.style.cssText = `
        padding: 12px;
        background: rgba(255, 255, 255, 0.1);
        display: flex;
        align-items: center;
        justify-content: space-between;
        cursor: move;
        user-select: none;
    `;

    // Title container
    const title = document.createElement('span');
    title.textContent = 'VoxDeck';
    title.style.cssText = `
        font-weight: bold;
        font-size: ${THEME.fontSize};
    `;

    // Controls container
    const controls = document.createElement('div');
    controls.style.cssText = `
        display: flex;
        align-items: center;
        gap: 8px;
    `;

    // Record button with mic icon
    const recordButton = document.createElement('button');
    recordButton.id = 'voxdeck-record-button';
    recordButton.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" fill="currentColor"/>
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" fill="currentColor"/>
        </svg>
    `;
    recordButton.style.cssText = `
        background: none;
        border: none;
        color: ${THEME.text};
        cursor: pointer;
        padding: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: 0.7;
        transition: opacity 0.2s;
    `;

    // Keyboard shortcut indicator
    const shortcut = document.createElement('span');
    shortcut.textContent = navigator.platform.includes('Mac') ? '⌘⇧Space' : 'Ctrl+Shift+Space';
    shortcut.style.cssText = `
        font-size: 12px;
        opacity: 0.7;
        background: rgba(255, 255, 255, 0.1);
        padding: 2px 6px;
        border-radius: 4px;
        margin-right: 8px;
    `;

    // Close button with X icon
    const closeButton = document.createElement('button');
    closeButton.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12 19 6.41z" fill="currentColor"/>
        </svg>
    `;
    closeButton.style.cssText = `
        background: none;
        border: none;
        color: ${THEME.text};
        cursor: pointer;
        padding: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: 0.7;
        transition: opacity 0.2s;
    `;

    controls.appendChild(shortcut);
    controls.appendChild(recordButton);
    controls.appendChild(closeButton);

    header.appendChild(title);
    header.appendChild(controls);

    // Create resize handles
    const handles = ['n', 'e', 's', 'w', 'ne', 'nw', 'se', 'sw'];
    handles.forEach(pos => {
        const handle = document.createElement('div');
        handle.className = `resize-${pos}`;
        handle.style.cssText = `
            position: absolute;
            z-index: 10001;
            background: transparent;
            ${pos.includes('n') ? 'top: -5px;' : ''}
            ${pos.includes('s') ? 'bottom: -5px;' : ''}
            ${pos.includes('e') ? 'right: -5px;' : ''}
            ${pos.includes('w') ? 'left: -5px;' : ''}
            ${pos.includes('n') || pos.includes('s') ? 'height: 10px;' : ''}
            ${pos.includes('e') || pos.includes('w') ? 'width: 10px;' : ''}
            ${pos.length === 2 ? 'width: 10px; height: 10px;' : ''}
            cursor: ${pos}-resize;
        `;
        container.appendChild(handle);
    });

    // Add dragging functionality
    let isDragging = false;
    let currentX;
    let currentY;
    let initialX;
    let initialY;

    header.addEventListener('mousedown', (e) => {
        isDragging = true;
        initialX = e.clientX - container.offsetLeft;
        initialY = e.clientY - container.offsetTop;
    });

    document.addEventListener('mousemove', (e) => {
        if (isDragging) {
            e.preventDefault();
            currentX = e.clientX - initialX;
            currentY = e.clientY - initialY;

            // Keep window within viewport bounds
            const maxX = window.innerWidth - container.offsetWidth;
            const maxY = window.innerHeight - container.offsetHeight;
            
            currentX = Math.max(0, Math.min(currentX, maxX));
            currentY = Math.max(0, Math.min(currentY, maxY));

            container.style.left = `${currentX}px`;
            container.style.top = `${currentY}px`;
            container.style.right = 'auto';
            container.style.bottom = 'auto';
        }
    });

    document.addEventListener('mouseup', () => {
        isDragging = false;
    });

    // Add resizing functionality
    let isResizing = false;
    let currentHandle = '';
    let originalWidth, originalHeight, originalX, originalY;
    let originalLeft, originalTop;

    handles.forEach(pos => {
        const handle = container.querySelector(`.resize-${pos}`);
        handle.addEventListener('mousedown', (e) => {
            isResizing = true;
            currentHandle = pos;
            const rect = container.getBoundingClientRect();
            originalWidth = rect.width;
            originalHeight = rect.height;
            originalX = e.clientX;
            originalY = e.clientY;
            originalLeft = rect.left;
            originalTop = rect.top;
            e.stopPropagation();
        });
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;

        const deltaX = e.clientX - originalX;
        const deltaY = e.clientY - originalY;
        let newWidth = originalWidth;
        let newHeight = originalHeight;
        let newLeft = originalLeft;
        let newTop = originalTop;

        if (currentHandle.includes('e')) {
            newWidth = Math.max(250, originalWidth + deltaX);
        }
        if (currentHandle.includes('w')) {
            const proposedWidth = Math.max(250, originalWidth - deltaX);
            if (proposedWidth !== newWidth) {
                newWidth = proposedWidth;
                newLeft = originalLeft + (originalWidth - proposedWidth);
            }
        }
        if (currentHandle.includes('s')) {
            newHeight = Math.max(200, originalHeight + deltaY);
        }
        if (currentHandle.includes('n')) {
            const proposedHeight = Math.max(200, originalHeight - deltaY);
            if (proposedHeight !== newHeight) {
                newHeight = proposedHeight;
                newTop = originalTop + (originalHeight - proposedHeight);
            }
        }

        // Apply size constraints
        newWidth = Math.min(newWidth, window.innerWidth - newLeft);
        newHeight = Math.min(newHeight, window.innerHeight - newTop);

        // Update container dimensions
        container.style.width = `${newWidth}px`;
        container.style.height = `${newHeight}px`;
        container.style.left = `${newLeft}px`;
        container.style.top = `${newTop}px`;

        // Update Three.js renderer size
        if (renderer && camera) {
            const visualizerContainer = document.querySelector('#voxdeck-visualizer');
            if (visualizerContainer && visualizerContainer.clientWidth > 0 && visualizerContainer.clientHeight > 0) {
                camera.aspect = visualizerContainer.clientWidth / visualizerContainer.clientHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(visualizerContainer.clientWidth, visualizerContainer.clientHeight, false);
            }
        }
    });

    document.addEventListener('mouseup', () => {
        isResizing = false;
        currentHandle = '';
    });

    // Create main content container
    const mainContent = document.createElement('div');
    mainContent.style.cssText = `
        flex: 1;
        display: flex;
        flex-direction: column;
        min-height: 0;
        position: relative;
    `;

    // Create visualizer container
    const visualizerContainer = document.createElement('div');
    visualizerContainer.id = 'voxdeck-visualizer';
    visualizerContainer.style.cssText = `
        width: 100%;
        height: 200px;
        position: relative;
        background: transparent;
        flex-shrink: 0;
        overflow: hidden;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    `;
    mainContent.appendChild(visualizerContainer);

    // Create text display area
    const textDisplay = document.createElement('div');
    textDisplay.id = 'voxdeck-text';
    textDisplay.style.cssText = `
        padding: 16px;
        flex: 1;
        min-height: 100px;
        overflow-y: auto;
        white-space: pre-wrap;
        position: relative;
        z-index: 1;
        font-size: 14px;
        line-height: 1.6;
        color: rgba(255, 255, 255, 0.9);
        background: transparent;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    `;
    mainContent.appendChild(textDisplay);

    // Add main content to container
    container.appendChild(header);
    container.appendChild(mainContent);

    // Initialize Three.js
    initThreeJS(visualizerContainer);

    // Event Listeners
    recordButton.addEventListener('click', async () => {
        if (isListening) {
            stopRecognition();
        } else {
            const initialized = await initializeRecognition();
            if (initialized) {
                startRecognition();
            }
        }
    });
    
    closeButton.addEventListener('click', () => {
        stopRecognition();
        container.remove();
    });

    // Add custom scrollbar and text styles
    const style = document.createElement('style');
    style.textContent = `
        #voxdeck-text::-webkit-scrollbar {
            width: 8px;
        }
        #voxdeck-text::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }
        #voxdeck-text::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 4px;
        }
        #voxdeck-text::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        .final-text {
            margin-bottom: 8px;
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        .interim-text {
            color: rgba(255, 255, 255, 0.6);
            font-style: italic;
            padding: 8px 12px;
        }
        #voxdeck-record-button.recording {
            color: #FF4444;
            background: rgba(255, 68, 68, 0.1);
        }
        #voxdeck-record-button.recording svg {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
    `;
    document.head.appendChild(style);

    document.body.appendChild(container);
    return container;
}

// Helper functions
function updateRecordButtonState(isRecording) {
    const button = document.querySelector('#voxdeck-record-button');
    if (button) {
        button.classList.toggle('recording', isRecording);
        button.innerHTML = isRecording ? '⏹️' : '🎤';
    }
}

function appendTranscript(finalText, interimText = '') {
    const display = document.querySelector('#voxdeck-text');
    if (!display) return;

    if (finalText) {
        const finalNode = document.createElement('div');
        finalNode.className = 'final-text';
        finalNode.textContent = finalText;
        
        // Add animation class
        finalNode.style.opacity = '0';
        finalNode.style.transform = 'translateY(10px)';
        display.appendChild(finalNode);
        
        // Trigger animation
        requestAnimationFrame(() => {
            finalNode.style.opacity = '1';
            finalNode.style.transform = 'translateY(0)';
        });
        
        display.scrollTop = display.scrollHeight;
    }

    const interimNode = display.querySelector('.interim-text') || document.createElement('div');
    interimNode.className = 'interim-text';
    interimNode.textContent = interimText;
    
    if (!interimNode.parentNode) {
        display.appendChild(interimNode);
    }
}

async function startRecognition() {
    if (!audioContext || audioContext.state === 'suspended') {
        const audioInitialized = await initAudio();
        if (!audioInitialized) {
            console.error('Failed to initialize audio');
            return;
        }
    }

    if (audioContext && audioContext.state === 'suspended') {
        await audioContext.resume();
    }

    if (recognition) {
        try {
            recognition.start();
            isListening = true;
            updateRecordButtonState(true);
        } catch (error) {
            console.error('Error starting recognition:', error);
        }
    }
}

function stopRecognition() {
    if (recognition) {
        recognition.stop();
    }
    if (audioContext) {
        audioContext.suspend();
    }
    isListening = false;
    updateRecordButtonState(false);
}

// Initialize when the page loads
document.addEventListener('DOMContentLoaded', createOrUpdateDisplay);

// Also run immediately in case DOM is already loaded
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    createOrUpdateDisplay();
}

// Remove any existing voice input button
function removeOldButton() {
  const oldButton = document.getElementById('voxdeck-toggle');
  if (oldButton) {
    oldButton.remove();
  }
}

// Listen for messages from the background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  removeOldButton(); // Always remove old button
  
  if (request.action === 'updateDisplay') {
    createOrUpdateDisplay(request.text);
    sendResponse({ success: true });
  } else if (request.action === 'requestMicrophoneAccess') {
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(() => sendResponse({ success: true }))
      .catch((error) => sendResponse({ success: false, error: error.message }));
    return true; // Required for async response
  } else if (request.action === 'startListening') {
    startRecognition();
    sendResponse({ success: true });
  } else if (request.action === 'stopListening') {
    stopRecognition();
    sendResponse({ success: true });
  }
  return true;
}); 