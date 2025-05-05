import os
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import datetime

# Configure logging
log_filename = f"voxdeck_nlp_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='🔍 %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Suppress oauth2client warning
logging.getLogger('oauth2client').setLevel(logging.ERROR)

# Load environment variables
load_dotenv()
PRESENTATION_ID = os.getenv("PRESENTATION_ID")
TOKEN_FILE = "token.json"
SCOPES = ["https://www.googleapis.com/auth/presentations"]

# Google Slides uses a different coordinate system
SLIDE_WIDTH = 9144000  # Standard 16:9 presentation width in EMU
SLIDE_HEIGHT = 5143500  # Standard 16:9 presentation height in EMU

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
    MOVE = "move"
    FORMAT = "format"

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
    THIRDS = [0.33, 0.66]
    
    # Determine horizontal position
    if x_center <= THIRDS[0]:
        h_pos = "left"
    elif x_center >= THIRDS[1]:
        h_pos = "right"
    else:
        h_pos = "center"
        
    # Determine vertical position
    if y_center <= THIRDS[0]:
        v_pos = "top"
    elif y_center >= THIRDS[1]:
        v_pos = "bottom"
    else:
        v_pos = "center"
    
    logger.info(f"  - Grid position: {v_pos}_{h_pos}")
    
    # Combine positions
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
    
    logger.info(f"Found {len(elements)} text elements total")
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
    """Resize an element by a scale factor."""
    service = get_slides_service()
    
    requests = [
        {
            "updatePageElementTransform": {
                "objectId": object_id,
                "transform": {
                    "scaleX": scale_factor,
                    "scaleY": scale_factor,
                },
                "applyMode": "RELATIVE"
            }
        }
    ]
    
    service.presentations().batchUpdate(
        presentationId=PRESENTATION_ID,
        body={"requests": requests}
    ).execute()
    
    return True

def parse_action(request: str) -> Tuple[ActionType, Dict[str, Any]]:
    """Parse the natural language request into an action type and parameters."""
    logger.info(f"Parsing request: '{request}'")
    request = request.lower()
    
    # Resize actions - enhanced for natural speech
    resize_increase = [
        'bigger', 'larger', 'increase size', 'make it bigger', 
        'expand', 'grow', 'enlarge', 'increase', 'make bigger'
    ]
    resize_decrease = [
        'smaller', 'decrease size', 'make it smaller', 'shrink', 
        'reduce', 'make smaller', 'decrease'
    ]
    
    if any(phrase in request for phrase in resize_increase):
        logger.info("Detected RESIZE (increase) action")
        return ActionType.RESIZE, {'scale_factor': 1.2}
    elif any(phrase in request for phrase in resize_decrease):
        logger.info("Detected RESIZE (decrease) action")
        return ActionType.RESIZE, {'scale_factor': 0.8}
    
    # Text change actions - enhanced for natural speech
    change_patterns = [
        "change to", "change it to", "make it say",
        "set it to", "replace with", "update to",
        "set to", "put", "write", "say"
    ]
    
    for pattern in change_patterns:
        if pattern in request:
            # Extract text after the pattern
            new_text = request.split(pattern)[-1].strip().strip("'").strip('"')
            logger.info(f"Detected CHANGE_TEXT action with new text: '{new_text}'")
            return ActionType.CHANGE_TEXT, {'new_text': new_text}
    
    # Special handling for team slide elements
    if "title" in request:
        # Assume they're referring to the main title
        logger.info("Detected reference to main title")
        if any(phrase in request for phrase in resize_increase + resize_decrease):
            scale_factor = 1.2 if any(phrase in request for phrase in resize_increase) else 0.8
            return ActionType.RESIZE, {'scale_factor': scale_factor}
        else:
            # Extract text after any word
            words = request.split()
            if len(words) > 2:  # Ensure there's content after "title"
                new_text = ' '.join(words[words.index("title")+1:]).strip().strip("'").strip('"')
                return ActionType.CHANGE_TEXT, {'new_text': new_text}
    
    logger.info("Could not determine action type from request")
    return None, {}

def process_text_request(request: str) -> str:
    """
    Process a natural language request to modify slides.
    Examples:
    - "Make the title bigger"
    - "Change the title to say 'Welcome to VoxDeck'"
    - "Make the text in the top right smaller"
    - "Set the bottom text to 'Hello World'"
    """
    logger.info("=" * 50)
    logger.info(f"Processing request: '{request}'")
    
    # Get all elements from the presentation
    elements = get_presentation_elements()
    if not elements:
        logger.info("No elements found in presentation")
        return "I don't see any text elements in the presentation."
    
    # Parse the action type and parameters
    action_type, params = parse_action(request)
    if not action_type:
        logger.info("Could not understand the requested action")
        return "I'm not sure what you want me to do. Try saying:\n" + \
               "- 'Make the title bigger'\n" + \
               "- 'Change the text to say [new text]'\n" + \
               "- 'Make the bottom part smaller'"
    
    # Find the target element
    target_element = None
    if any(word in request.lower() for word in ['title', 'top', 'bottom', 'left', 'right', 'center', 'up', 'down']):
        target_element = find_element_by_position(elements, request)
    else:
        # Default to title if no position specified
        logger.info("No position specified, looking for title element")
        for element in elements.values():
            if "meet the voxdeck team" in element.content.lower():
                target_element = element
                break
        if not target_element:
            target_element = next(iter(elements.values()))
    
    if not target_element:
        logger.info("Could not find a matching element")
        return "I couldn't find the text you're referring to. Try being more specific about where it is (title, top, bottom, etc.)"
    
    try:
        # Execute the requested action
        if action_type == ActionType.RESIZE:
            resize_element(target_element.object_id, params['scale_factor'])
            action_desc = "bigger" if params['scale_factor'] > 1 else "smaller"
            logger.info(f"Successfully made element {action_desc}")
            return f"Done! I've made the text {action_desc}"
        
        elif action_type == ActionType.CHANGE_TEXT:
            update_element_text(target_element.object_id, params['new_text'])
            logger.info(f"Successfully updated text to: '{params['new_text']}'")
            return f"Done! I've updated the text"
        
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