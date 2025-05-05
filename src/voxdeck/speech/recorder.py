import numpy as np
import sounddevice as sd
from pathlib import Path
import wave
import threading
import queue
import logging
from typing import Optional
import time

logger = logging.getLogger(__name__)

class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.recording = False
        self.audio_queue = queue.Queue()
        self.recorded_data = []
        
    def callback(self, indata, frames, time, status):
        """Callback for sounddevice to handle incoming audio data"""
        if status:
            logger.warning(f"Audio callback status: {status}")
        self.audio_queue.put(indata.copy())
        self.recorded_data.extend(indata.flatten())
    
    def start_recording(self):
        """Start recording audio"""
        self.recording = True
        self.recorded_data = []
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            callback=self.callback
        )
        self.stream.start()
        logger.info("Started recording audio")
    
    def stop_recording(self) -> Optional[str]:
        """Stop recording and save to file"""
        if not self.recording:
            return None
            
        self.recording = False
        self.stream.stop()
        self.stream.close()
        
        # Convert to numpy array
        audio_data = np.array(self.recorded_data)
        
        # Save to WAV file
        output_dir = Path("temp_audio")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "recording.wav"
        
        with wave.open(str(output_file), 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit audio
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.astype(np.int16).tobytes())
        
        logger.info(f"Saved recording to {output_file}")
        return str(output_file)

class VoiceDetector:
    def __init__(self, 
                 silence_threshold: float = 0.02,
                 silence_duration: float = 1.0,
                 max_duration: float = 10.0):
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.max_duration = max_duration
        self.recorder = AudioRecorder()
        
    def detect_speech(self) -> Optional[str]:
        """Record until silence is detected or max duration is reached"""
        self.recorder.start_recording()
        
        silence_start = None
        start_time = time.time()
        
        while True:
            if not self.recorder.audio_queue.empty():
                data = self.recorder.audio_queue.get()
                level = np.abs(data).mean()
                
                # Check for silence
                if level < self.silence_threshold:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > self.silence_duration:
                        break
                else:
                    silence_start = None
                    
            # Check max duration
            if time.time() - start_time > self.max_duration:
                break
                
            time.sleep(0.1)
        
        return self.recorder.stop_recording() 