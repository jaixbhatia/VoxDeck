import openai
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class WhisperTranscriber:
    def __init__(self, api_key: str):
        """Initialize the Whisper transcriber with OpenAI API key"""
        openai.api_key = api_key
        
    def transcribe(self, audio_file: str) -> Optional[str]:
        """
        Transcribe audio file using OpenAI's Whisper API
        
        Args:
            audio_file: Path to the audio file
            
        Returns:
            Transcribed text or None if transcription failed
        """
        try:
            audio_path = Path(audio_file)
            if not audio_path.exists():
                logger.error(f"Audio file not found: {audio_file}")
                return None
                
            logger.info(f"Transcribing audio file: {audio_file}")
            with open(audio_file, "rb") as f:
                transcript = openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="text"
                )
            
            logger.info(f"Transcription result: {transcript}")
            return transcript
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return None 