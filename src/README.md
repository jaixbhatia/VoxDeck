# VoxDeck

Voice control for Google Slides presentations. Edit your slides naturally using voice commands.

## Features

- Voice command recognition using OpenAI Whisper
- Natural language processing for slide editing
- Support for text editing, resizing, and positioning
- Continuous listening mode
- Direct text command mode for testing

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/voxdeck.git
cd voxdeck/src
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install the package:
```bash
pip install -e .
```

## Configuration

Create a `.env` file in your project directory with:

```env
OPENAI_API_KEY=your_openai_api_key
GOOGLE_CREDENTIALS=path_to_your_google_credentials.json
PRESENTATION_ID=your_google_slides_presentation_id
```

## Usage

### Voice Commands

Start listening for voice commands:
```bash
voxdeck listen
```

For continuous listening mode:
```bash
voxdeck listen --continuous
```

### Text Commands

Test commands directly without voice:
```bash
voxdeck text "make the title bigger"
```

### Example Commands

- "Make the title bigger"
- "Change the text in the top right to say 'Hello World'"
- "Make the bottom text smaller"
- "Set the text up there to 'Welcome'"

## Development

1. Install development dependencies:
```bash
pip install -e ".[dev]"
```

2. Run tests:
```bash
pytest
```

## License

MIT License 