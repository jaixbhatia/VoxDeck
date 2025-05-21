vibe coding for google slides. built for people who already have a deck and just want to tweak it fast — without breaking their rhythm.

## Demo Video


https://github.com/user-attachments/assets/ac72e0b2-f772-4e1f-b863-dcad6ae2a772


## Features

- 🔄 Resize elements and images with aspect ratio preservation
- 🎯 Maintain element positioning during transformations
- 📝 Comprehensive error handling and logging
- 🔒 Secure credential management
- 📚 Well-documented API with type hints

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/google-slides-utils.git
cd google-slides-utils
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Google API credentials:
   - Go to the [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select an existing one
   - Enable the Google Slides API
   - Create a service account and download the credentials JSON file
   - Store the credentials file securely

4. Set up environment variables:
   Create a `.env` file in the root directory with the following variables:
   ```env
   # Google API credentials
   GOOGLE_CREDENTIALS_PATH=path/to/your/credentials.json
   
   # Google Slides Presentation ID (from the URL of your presentation)
   # Example: https://docs.google.com/presentation/d/PRESENTATION_ID/edit
   PRESENTATION_ID=your_presentation_id
   
   # Optional: OpenAI API key (if using AI features)
   OPENAI_API_KEY=your_openai_api_key
   ```

5. Configure credentials.json:
   - Place your downloaded `credentials.json` file under VoxDeck/backend/app

## Usage

```python
from google_slides_utils import initialize_slides_api, resize_image

# Initialize the API client
initialize_slides_api('path/to/credentials.json')

# Resize an image in your presentation
response = resize_image(
    presentation_id='your_presentation_id',
    image_id='your_image_id',
    scale_factor=1.5  # Increase size by 50%
)
```

## API Reference

### `initialize_slides_api(credentials_path: str) -> None`
Initialize the Google Slides API client with credentials.

### `resize_element(presentation_id: str, element_id: str, scale_factor: float) -> Optional[Dict]`
Resize any element while maintaining its aspect ratio and center position.

### `resize_image(presentation_id: str, image_id: str, scale_factor: float) -> Optional[Dict]`
Resize an image while maintaining its aspect ratio.

### `get_image_elements(presentation_id: str, page_id: str) -> List[Dict]`
Get all image elements on a specific page of a presentation.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
