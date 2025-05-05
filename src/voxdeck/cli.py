import click
import os
from pathlib import Path
from rich.console import Console
from rich.logging import RichHandler
from dotenv import load_dotenv
import logging
from .speech.recorder import VoiceDetector
from .speech.transcriber import WhisperTranscriber
from .slides.editor import SlideEditor

# Configure rich logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("voxdeck")

console = Console()

def setup_environment():
    """Load environment variables and check required ones"""
    load_dotenv()
    
    required_vars = [
        "OPENAI_API_KEY",
        "GOOGLE_CREDENTIALS",
        "PRESENTATION_ID"
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise click.ClickException(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Please set them in your .env file"
        )

@click.group()
def cli():
    """VoxDeck - Voice control for Google Slides"""
    pass

@cli.command()
@click.option('--continuous', is_flag=True, help='Keep listening for commands')
def listen(continuous: bool):
    """Start listening for voice commands"""
    try:
        setup_environment()
        
        detector = VoiceDetector()
        transcriber = WhisperTranscriber(os.getenv("OPENAI_API_KEY"))
        editor = SlideEditor()
        
        def process_command():
            with console.status("Listening for command..."):
                audio_file = detector.detect_speech()
                if not audio_file:
                    return False
                    
            with console.status("Transcribing..."):
                text = transcriber.transcribe(audio_file)
                if not text:
                    console.print("[red]Failed to transcribe audio[/red]")
                    return False
                    
            console.print(f"[green]Heard:[/green] {text}")
            
            with console.status("Processing command..."):
                result = editor.process_command(text)
                console.print(f"[blue]Result:[/blue] {result}")
            
            return True
        
        if continuous:
            console.print("[yellow]Starting continuous listening mode. Press Ctrl+C to stop.[/yellow]")
            try:
                while True:
                    process_command()
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopping...[/yellow]")
        else:
            process_command()
            
    except Exception as e:
        logger.exception("Error in voice command processing")
        raise click.ClickException(str(e))

@cli.command()
@click.argument('command')
def text(command: str):
    """Process a text command directly"""
    try:
        setup_environment()
        editor = SlideEditor()
        result = editor.process_command(command)
        console.print(f"[blue]Result:[/blue] {result}")
    except Exception as e:
        logger.exception("Error processing text command")
        raise click.ClickException(str(e))

if __name__ == '__main__':
    cli() 