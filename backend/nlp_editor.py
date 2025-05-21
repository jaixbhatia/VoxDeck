import os
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dotenv import load_dotenv
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import datetime

# Configure logging
log_filename = "voxdeck.log"
logging.basicConfig(
    level=logging.INFO,
    format='🔍 %(message)s',
    handlers=[
        logging.FileHandler(log_filename, mode='w'),  # 'w' mode overwrites the file
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Suppress oauth2client warning
logging.getLogger('oauth2client').setLevel(logging.ERROR)

# Load environment variables
load_dotenv()
PRESENTATION_ID = os.getenv("PRESENTATION_ID")

# Get absolute paths for credential files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/presentations"]

# Google Slides uses a different coordinate system
SLIDE_WIDTH = 9144000  # Standard 16:9 presentation width in EMU
SLIDE_HEIGHT = 5143500  # Standard 16:9 presentation height in EMU

# Color definitions
COLORS = {
    "green": {"red": 0, "green": 1, "blue": 0},
    "red": {"red": 1, "green": 0, "blue": 0},
    "blue": {"red": 0, "green": 0, "blue": 1},
    "black": {"red": 0, "green": 0, "blue": 0},
    "white": {"red": 1, "green": 1, "blue": 1}
}

class ElementType(Enum):
    TEXT = "text"
    SHAPE = "shape"
    IMAGE = "image"

class Position(Enum):
    TOP_LEFT = "top_left"
    TOP = "top"
    TOP_RIGHT = "top_right"
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM = "bottom"
    BOTTOM_RIGHT = "bottom_right"

@dataclass
class SlideElement:
    object_id: str
    element_type: ElementType
    content: str
    position: Dict[str, float]  # x, y coordinates
    size: Dict[str, float]      # width, height
    page_number: int

class ActionType(Enum):
    CHANGE_TEXT = "change_text"
    RESIZE = "resize"
    CHANGE_FONT = "change_font"
    CHANGE_COLOR = "change_color"

def authenticate_google_slides():
    """Authenticate with Google Slides API."""
    creds = None
    
    # Check if token file exists
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # If no valid credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"credentials.json file not found at {CREDENTIALS_FILE}. Please download it from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    return creds

def get_slides_service():
    """Initialize and return the Google Slides service."""
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError("Token file not found. Please run authentication first.")
    
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    return build("slides", "v1", credentials=creds)

def get_position_from_coordinates(x: float, y: float, width: float, height: float) -> Position:
    """
    Determine the position category based on coordinates.
    Uses a 3x3 grid system to map positions:
    
    TOP_LEFT     TOP     TOP_RIGHT
    LEFT         CENTER  RIGHT
    BOTTOM_LEFT  BOTTOM  BOTTOM_RIGHT
    """
    # Convert coordinates to relative positions (0-1)
    # Add half the width/height to get the center point
    x_center = (x + width/2) / SLIDE_WIDTH
    y_center = (y + height/2) / SLIDE_HEIGHT
    
    logger.info(f"Position analysis for ({x}, {y}):")
    logger.info(f"  - Relative center point: ({x_center:.2f}, {y_center:.2f})")
    
    # Define the grid sections
    HORIZONTAL = [0.33, 0.66]  # Divide into thirds horizontally
    
    # Determine horizontal position
    if x_center <= HORIZONTAL[0]:
        h_pos = "left"
    elif x_center >= HORIZONTAL[1]:
        h_pos = "right"
    else:
        h_pos = "center"
        
    # Determine vertical position with more precise boundaries for top
    if y_center <= 0.33:  # Top third
        v_pos = "top"
    elif y_center >= 0.66:  # Bottom third
        v_pos = "bottom"
    else:
        v_pos = "center"
    
    logger.info(f"  - Grid position: {v_pos}_{h_pos}")
    
    # Combine positions with priority to vertical position
    if v_pos == "center" and h_pos == "center":
        position_str = "center"
    elif v_pos == "center":
        position_str = h_pos
    elif h_pos == "center":
        position_str = v_pos
    else:
        position_str = f"{v_pos}_{h_pos}"
    
    try:
        return Position(position_str)
    except ValueError:
        logger.info(f"  - Could not map '{position_str}' to enum, defaulting to CENTER")
        return Position.CENTER

def get_presentation_elements() -> Dict[str, SlideElement]:
    """Get all elements from the presentation with their positions and properties."""
    service = get_slides_service()
    presentation = service.presentations().get(
        presentationId=PRESENTATION_ID
    ).execute()
    
    logger.info("Scanning presentation elements...")
    elements = {}
    for page_number, slide in enumerate(presentation.get('slides', []), 1):
        logger.info(f"Processing slide {page_number}")
        for element in slide.get('pageElements', []):
            element_id = element.get('objectId')
            
            # Get position and size
            transform = element.get('transform', {})
            position = {
                'x': transform.get('translateX', 0),
                'y': transform.get('translateY', 0)
            }
            size = {
                'width': element.get('size', {}).get('width', {}).get('magnitude', 0),
                'height': element.get('size', {}).get('height', {}).get('magnitude', 0)
            }
            
            # Handle different element types
            if 'shape' in element and 'text' in element['shape']:
                text_content = ''
                for text_element in element['shape']['text'].get('textElements', []):
                    if 'textRun' in text_element:
                        text_content += text_element['textRun'].get('content', '')
                
                text_content = text_content.strip()
                if text_content:  # Only process elements with actual text
                    logger.info(f"Found text element: '{text_content[:50]}' at ({position['x']}, {position['y']})")
                    logger.info(f"Element size: {size['width']} x {size['height']}")
                    
                    slide_element = SlideElement(
                        object_id=element_id,
                        element_type=ElementType.TEXT,
                        content=text_content,
                        position=position,
                        size=size,
                        page_number=page_number
                    )
                    elements[element_id] = slide_element
            
            # Handle image elements
            elif 'image' in element:
                logger.info(f"Found image element at ({position['x']}, {position['y']})")
                logger.info(f"Image size: {size['width']} x {size['height']}")
                
                slide_element = SlideElement(
                    object_id=element_id,
                    element_type=ElementType.IMAGE,
                    content="[Image]",  # Use a placeholder for image content
                    position=position,
                    size=size,
                    page_number=page_number
                )
                elements[element_id] = slide_element
    
    logger.info(f"Found {len(elements)} elements total")
    return elements

def find_element_by_position(elements: Dict[str, SlideElement], target_position: str) -> SlideElement:
    """Find an element based on position description."""
    logger.info(f"Looking for element matching position: {target_position}")
    
    # Enhanced position keywords for natural speech
    position_keywords = {
        'top': ['top', 'upper', 'above', 'up', 'top of', 'upper part', 'at the top'],
        'bottom': ['bottom', 'lower', 'below', 'down', 'bottom of', 'lower part', 'at the bottom'],
        'left': ['left', 'leftmost', 'beginning', 'start', 'left side', 'on the left'],
        'right': ['right', 'rightmost', 'end', 'right side', 'on the right'],
        'center': ['center', 'middle', 'centered', 'centre', 'in the middle']
    }
    
    # Special handling for title
    if "title" in target_position.lower():
        logger.info("Looking for main title element")
        # Find the element with "welcome to voxdeck" content
        for element in elements.values():
            if "welcome to voxdeck" in element.content.lower():
                logger.info(f"Found title element: {element.content}")
                return element
    
    # Parse the position from the description
    target_pos_parts = set()  # Using set to avoid duplicates
    for pos, keywords in position_keywords.items():
        if any(keyword in target_position.lower() for keyword in keywords):
            target_pos_parts.add(pos)
            logger.info(f"Matched position keyword: {pos}")
    
    # Convert set to sorted list for consistent ordering
    target_pos_parts = sorted(target_pos_parts)
    target_pos_str = '_'.join(target_pos_parts) or 'center'
    
    try:
        target_pos = Position(target_pos_str)
        logger.info(f"Looking for elements in position: {target_pos.value}")
    except ValueError:
        logger.info(f"Could not resolve position '{target_pos_str}', defaulting to CENTER")
        target_pos = Position.CENTER
    
    # Find matching elements
    matching_elements = []
    for element in elements.values():
        element_pos = get_position_from_coordinates(
            element.position['x'],
            element.position['y'],
            element.size['width'],
            element.size['height']
        )
        if element_pos == target_pos:
            matching_elements.append(element)
            logger.info(f"Found matching element: '{element.content[:50]}'")
    
    if not matching_elements:
        # If no exact match, try to find elements in the general area
        logger.info("No exact position matches, looking for elements in the general area")
        for element in elements.values():
            pos = get_position_from_coordinates(
                element.position['x'],
                element.position['y'],
                element.size['width'],
                element.size['height']
            )
            # Check if the position contains any of our target position parts
            pos_parts = pos.value.split('_')
            if any(part in pos_parts for part in target_pos_str.split('_')):
                matching_elements.append(element)
                logger.info(f"Found partial match: '{element.content[:50]}' at position {pos.value}")
    
    if not matching_elements:
        logger.info("No elements found in the specified position")
        return None
    
    # If multiple matches, prefer elements with more content
    matching_elements.sort(key=lambda x: len(x.content), reverse=True)
    return matching_elements[0]

def update_element_text(object_id: str, new_text: str):
    """Update the text of a specific element."""
    service = get_slides_service()
    
    requests = [
        {
            "deleteText": {
                "objectId": object_id,
                "textRange": {"type": "ALL"}
            }
        },
        {
            "insertText": {
                "objectId": object_id,
                "insertionIndex": 0,
                "text": new_text
            }
        }
    ]
    
    service.presentations().batchUpdate(
        presentationId=PRESENTATION_ID,
        body={"requests": requests}
    ).execute()
    
    return True

def resize_element(object_id: str, scale_factor: float):
    """Resize an element by adjusting size or font size depending on type."""
    service = get_slides_service()
    
    # Get current element properties
    presentation = service.presentations().get(
        presentationId=PRESENTATION_ID
    ).execute()
    
    # Find the element
    element = None
    for slide in presentation.get('slides', []):
        for page_element in slide.get('pageElements', []):
            if page_element.get('objectId') == object_id:
                element = page_element
                break
        if element:
            break
    
    if not element:
        raise ValueError(f"Element {object_id} not found")
    
    # Check if it's a text element
    if 'shape' in element and 'text' in element['shape']:
        logger.info("Resizing text element by adjusting font size")
        text_elements = element.get('shape', {}).get('text', {}).get('textElements', [])
        if not text_elements:
            logger.error("No text elements found in shape")
            return False
            
        current_style = text_elements[0].get('textRun', {}).get('style', {})
        current_font_size = current_style.get('fontSize', {}).get('magnitude', 12)
        logger.info(f"Current font size: {current_font_size}pt")
        
        # Calculate new font size
        new_font_size = current_font_size + 5
        logger.info(f"Setting new font size to: {new_font_size}pt")
        
        requests = [{
            "updateTextStyle": {
                "objectId": object_id,
                "textRange": {
                    "type": "ALL"
                },
                "style": {
                    "fontSize": {
                        "magnitude": new_font_size,
                        "unit": "PT"
                    }
                },
                "fields": "fontSize"
            }
        }]
    
    # Handle image elements
    elif 'image' in element:
        logger.info("Resizing image element by adjusting dimensions")
        current_transform = element.get('transform', {})
        
        # Get current scale if it exists, otherwise use 1 as default
        current_scale_x = current_transform.get('scaleX', 1)
        current_scale_y = current_transform.get('scaleY', 1)
        
        # Calculate new scale by multiplying current scale with scale factor
        new_scale_x = current_scale_x * scale_factor
        new_scale_y = current_scale_y * scale_factor
        
        # Keep the current position
        current_x = current_transform.get('translateX', 0)
        current_y = current_transform.get('translateY', 0)
        
        logger.info(f"Current scale: ({current_scale_x}, {current_scale_y})")
        logger.info(f"New scale: ({new_scale_x}, {new_scale_y})")
        logger.info(f"Position: ({current_x}, {current_y})")
        
        requests = [{
            "updatePageElementTransform": {
                "objectId": object_id,
                "transform": {
                    "scaleX": new_scale_x,
                    "scaleY": new_scale_y,
                    "translateX": current_x,
                    "translateY": current_y,
                    "unit": "EMU"
                },
                "applyMode": "ABSOLUTE"
            }
        }]
    
    try:
        logger.info(f"Sending update request: {requests}")
        response = service.presentations().batchUpdate(
            presentationId=PRESENTATION_ID,
            body={"requests": requests}
        ).execute()
        logger.info(f"API Response: {response}")
        return True
    except Exception as e:
        logger.error(f"Error resizing element: {str(e)}")
        raise

def update_font_family(object_id: str, font_family: str):
    """Update the font family of a specific element."""
    service = get_slides_service()
    
    requests = [{
        "updateTextStyle": {
            "objectId": object_id,
            "textRange": {
                "type": "ALL"
            },
            "style": {
                "fontFamily": font_family
            },
            "fields": "fontFamily"
        }
    }]
    
    service.presentations().batchUpdate(
        presentationId=PRESENTATION_ID,
        body={"requests": requests}
    ).execute()
    
    return True

def update_text_color(object_id: str, color: Dict[str, Any]):
    """Update the text color of a specific element."""
    service = get_slides_service()
    
    requests = [{
        "updateTextStyle": {
            "objectId": object_id,
            "textRange": {
                "type": "ALL"
            },
            "style": {
                "foregroundColor": {
                    "opaqueColor": {
                        "rgbColor": color
                    }
                }
            },
            "fields": "foregroundColor"
        }
    }]
    
    service.presentations().batchUpdate(
        presentationId=PRESENTATION_ID,
        body={"requests": requests}
    ).execute()
    
    return True

def parse_action(request: str) -> Tuple[ActionType, Dict[str, Any]]:
    """Parse the natural language request into an action type and parameters."""
    logger.info(f"Parsing request: '{request}'")
    request = request.lower().strip()
    
    # Color change patterns - check these before text changes
    color_patterns = [
        "make it", "change color to", "set color to",
        "change to", "make text", "set text color to",
        "change text color to", "make the text", "change the color",
        "set the color", "color the text"
    ]
    
    # First check for color changes since they're more specific
    for color_name, rgb_values in COLORS.items():
        if color_name in request:
            # Check if any color pattern is present
            for pattern in color_patterns:
                if pattern in request:
                    logger.info(f"Detected CHANGE_COLOR action with color: '{color_name}'")
                    return ActionType.CHANGE_COLOR, {'color': rgb_values}
    
    # Font change patterns
    font_patterns = [
        "change font to", "set font to", "make font",
        "change to font", "use font", "switch to font",
        "make all fonts", "change all fonts to", "set all fonts to",
        "make fonts", "change fonts to", "set fonts to"
    ]
    
    # Check for font changes
    for pattern in font_patterns:
        if pattern in request:
            parts = request.split(pattern)
            if len(parts) > 1:
                font_name = parts[1].strip().strip("'").strip('"')
                logger.info(f"Detected CHANGE_FONT action with font: '{font_name}'")
                return ActionType.CHANGE_FONT, {'font_family': font_name}
            # Special case for when font name comes right after "make all fonts" without "to"
            elif pattern == "make all fonts" or pattern == "make fonts":
                remaining_text = request.replace(pattern, "").strip()
                if remaining_text:
                    logger.info(f"Detected CHANGE_FONT action with font: '{remaining_text}'")
                    return ActionType.CHANGE_FONT, {'font_family': remaining_text}
    
    # Change text actions - enhanced for natural speech
    change_patterns = [
        "change to", "change it to", "make it say",
        "set it to", "replace with", "update to",
        "set to", "change the text to say", "change the text to",
        "change to say", "say"
    ]
    
    # Check for text changes
    for pattern in change_patterns:
        if pattern in request:
            # Split by the pattern and get the text after it
            parts = request.split(pattern)
            if len(parts) > 1:
                new_text = parts[1].strip().strip("'").strip('"')
                logger.info(f"Detected CHANGE_TEXT action with new text: '{new_text}'")
                return ActionType.CHANGE_TEXT, {'new_text': new_text}
    
    # If no pattern matched but contains "change" and "to", try to extract text
    if "change" in request and "to" in request:
        text_after_to = request.split("to")[-1].strip().strip("'").strip('"')
        if text_after_to:
            logger.info(f"Detected CHANGE_TEXT action with new text: '{text_after_to}'")
            return ActionType.CHANGE_TEXT, {'new_text': text_after_to}
    
    # Resize actions - enhanced for natural speech
    resize_increase = [
        'bigger', 'larger', 'increase size', 'make it bigger', 
        'expand', 'grow', 'enlarge', 'increase', 'make bigger',
        'increase the size', 'make it larger', 'make the image bigger',
        'increase image size', 'enlarge the image', 'make image bigger'
    ]
    resize_decrease = [
        'smaller', 'decrease size', 'make it smaller', 'shrink', 
        'reduce', 'make smaller', 'decrease', 'reduce size',
        'decrease the size', 'make it reduce', 'make the image smaller',
        'decrease image size', 'shrink the image', 'make image smaller'
    ]
    
    if any(phrase in request for phrase in resize_increase):
        logger.info("Detected RESIZE (increase) action")
        return ActionType.RESIZE, {'scale_factor': 1.2}
    elif any(phrase in request for phrase in resize_decrease):
        logger.info("Detected RESIZE (decrease) action")
        return ActionType.RESIZE, {'scale_factor': 0.8}
    
    logger.info("Could not determine action type from request")
    return None, {}

def update_element_position(object_id: str, target_position: Position):
    """Update the position of an element on the slide."""
    service = get_slides_service()
    
    # Get current element properties
    presentation = service.presentations().get(
        presentationId=PRESENTATION_ID
    ).execute()
    
    # Find the element
    element = None
    for slide in presentation.get('slides', []):
        for page_element in slide.get('pageElements', []):
            if page_element.get('objectId') == object_id:
                element = page_element
                break
        if element:
            break
    
    if not element:
        raise ValueError(f"Element {object_id} not found")
    
    # Get current transform
    current_transform = element.get('transform', {})
    current_scale_x = current_transform.get('scaleX', 1)
    current_scale_y = current_transform.get('scaleY', 1)
    
    # Define positions mapping (in EMU units)
    positions = {
        Position.TOP: {'x': SLIDE_WIDTH / 2, 'y': 100000},
        Position.BOTTOM: {'x': SLIDE_WIDTH / 2, 'y': SLIDE_HEIGHT - 500000},
        Position.LEFT: {'x': 100000, 'y': SLIDE_HEIGHT / 2},
        Position.RIGHT: {'x': SLIDE_WIDTH - 100000, 'y': SLIDE_HEIGHT / 2},
        Position.CENTER: {'x': SLIDE_WIDTH / 2, 'y': SLIDE_HEIGHT / 2},
        Position.TOP_LEFT: {'x': 100000, 'y': 100000},
        Position.TOP_RIGHT: {'x': SLIDE_WIDTH - 100000, 'y': 100000},
        Position.BOTTOM_LEFT: {'x': 100000, 'y': SLIDE_HEIGHT - 100000},
        Position.BOTTOM_RIGHT: {'x': SLIDE_WIDTH - 100000, 'y': SLIDE_HEIGHT - 100000}
    }
    
    # Get target position
    new_pos = positions.get(target_position)
    if not new_pos:
        raise ValueError(f"Invalid position: {target_position}")
    
    logger.info(f"Moving element to position: {target_position.value}")
    logger.info(f"New coordinates: ({new_pos['x']}, {new_pos['y']})")
    
    requests = [{
        "updatePageElementTransform": {
            "objectId": object_id,
            "transform": {
                "scaleX": current_scale_x,
                "scaleY": current_scale_y,
                "translateX": new_pos['x'],
                "translateY": new_pos['y'],
                "unit": "EMU"
            },
            "applyMode": "ABSOLUTE"
        }
    }]
    
    try:
        response = service.presentations().batchUpdate(
            presentationId=PRESENTATION_ID,
            body={"requests": requests}
        ).execute()
        logger.info(f"Move response: {response}")
        return True
    except Exception as e:
        logger.error(f"Error moving element: {str(e)}")
        raise

def process_text_request(request: str) -> str:
    """
    Process a natural language request to modify slides.
    Examples:
    - "Make the title bigger"
    - "Change the title to say 'Welcome to VoxDeck'"
    - "Make the text in the top right smaller"
    - "Set the bottom text to 'Hello World'"
    - "Make all fonts Helvetica"
    - "Make the image bigger"
    """
    logger.info("=" * 50)
    logger.info(f"Processing request: '{request}'")
    
    # Get all elements from the presentation
    elements = get_presentation_elements()
    if not elements:
        logger.info("No elements found in presentation")
        return "I don't see any elements in the presentation."
    
    # Parse the action type and parameters
    action_type, params = parse_action(request)
    
    # Check for move/position-related keywords
    move_keywords = ['move', 'place', 'put', 'position', 'relocate']
    position_keywords = {
        'bottom': Position.BOTTOM,
        'top': Position.TOP,
        'left': Position.LEFT,
        'right': Position.RIGHT,
        'center': Position.CENTER
    }
    
    # Handle move requests
    if any(keyword in request.lower() for keyword in move_keywords):
        # Determine target position
        target_pos = None
        for pos_keyword, pos_value in position_keywords.items():
            if pos_keyword in request.lower():
                target_pos = pos_value
                break
        
        if target_pos:
            # Find the element to move (prioritize title/text elements)
            target_element = None
            for element in elements.values():
                if element.element_type == ElementType.TEXT:
                    if "title" in request.lower() and "welcome to voxdeck" in element.content.lower():
                        target_element = element
                        break
                    # If no specific title mentioned, use the first text element
                    if not target_element:
                        target_element = element
            
            if target_element:
                try:
                    update_element_position(target_element.object_id, target_pos)
                    return f"Done! I've moved the text to the {target_pos.value} of the slide"
                except Exception as e:
                    logger.error(f"Error moving element: {str(e)}")
                    return f"Sorry, I ran into an error while moving the text: {str(e)}"
            else:
                return "I couldn't find the text element to move"
    
    # Handle other action types as before...
    if not action_type:
        logger.info("Could not understand the requested action")
        return "I'm not sure what you want me to do. Try saying:\n" + \
               "- 'Make the title bigger'\n" + \
               "- 'Change the text to say [new text]'\n" + \
               "- 'Make all fonts [font name]'\n" + \
               "- 'Make the image bigger'"
    
    # Special handling for changing all fonts
    if action_type == ActionType.CHANGE_FONT and "all" in request.lower():
        success_count = 0
        for element in elements.values():
            try:
                update_font_family(element.object_id, params['font_family'])
                success_count += 1
            except Exception as e:
                logger.error(f"Error updating font for element {element.object_id}: {str(e)}")
        
        if success_count > 0:
            logger.info(f"Successfully updated font to '{params['font_family']}' for {success_count} elements")
            return f"Done! I've updated the font to {params['font_family']} for {success_count} elements"
        else:
            return "Sorry, I wasn't able to update any fonts"

    # Find the target element based on the request type
    target_element = None
    
    # Check if this is an image-related request
    if "image" in request.lower():
        logger.info("Looking for image element")
        for element in elements.values():
            if element.element_type == ElementType.IMAGE:
                target_element = element
                logger.info("Found image element to modify")
                break
    # Otherwise look for text elements by position
    elif any(word in request.lower() for word in ['title', 'top', 'bottom', 'left', 'right', 'center', 'up', 'down']):
        target_element = find_element_by_position(elements, request)
    else:
        # Default to title if no position specified
        logger.info("No position specified, looking for title element")
        for element in elements.values():
            if element.element_type == ElementType.TEXT and "welcome to voxdeck" in element.content.lower():
                target_element = element
                break
        if not target_element:
            target_element = next(iter(elements.values()))
    
    if not target_element:
        logger.info("Could not find a matching element")
        return "I couldn't find the element you're referring to. Try being more specific about what you want to modify."
    
    try:
        # Execute the requested action
        if action_type == ActionType.RESIZE:
            resize_element(target_element.object_id, params['scale_factor'])
            action_desc = "bigger" if params['scale_factor'] > 1 else "smaller"
            element_type = "image" if target_element.element_type == ElementType.IMAGE else "text"
            logger.info(f"Successfully made {element_type} {action_desc}")
            return f"Done! I've made the {element_type} {action_desc}"
        
        elif action_type == ActionType.CHANGE_TEXT:
            update_element_text(target_element.object_id, params['new_text'])
            logger.info(f"Successfully updated text to: '{params['new_text']}'")
            return f"Done! I've updated the text"
        
        elif action_type == ActionType.CHANGE_FONT:
            update_font_family(target_element.object_id, params['font_family'])
            logger.info(f"Successfully updated font to: '{params['font_family']}'")
            return f"Done! I've updated the font to {params['font_family']}"
            
        elif action_type == ActionType.CHANGE_COLOR:
            update_text_color(target_element.object_id, params['color'])
            color_name = next(name for name, rgb in COLORS.items() if rgb == params['color'])
            logger.info(f"Successfully updated text color to: '{color_name}'")
            return f"Done! I've updated the text color to {color_name}"
        
    except Exception as e:
        logger.error(f"Error performing action: {str(e)}")
        return f"Sorry, I ran into an error: {str(e)}"
    
    return "Done!"

if __name__ == "__main__":
    # Example usage
    examples = [
        "Change the text in the top right to say 'holy shit this is working'",
    ]
    
    for example in examples:
        result = process_text_request(example)
        print(f"\nResult: {result}") 