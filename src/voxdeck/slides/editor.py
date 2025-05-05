import os
import logging
from typing import Dict, Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from ..core.models import (
    SlideElement,
    ElementType,
    Position,
    ActionType,
    VoiceCommand
)

logger = logging.getLogger(__name__)

class SlideEditor:
    """Handles all Google Slides operations"""
    
    def __init__(self):
        self.presentation_id = os.getenv("PRESENTATION_ID")
        self.credentials_file = os.getenv("GOOGLE_CREDENTIALS")
        self.token_file = "token.json"
        self.scopes = ["https://www.googleapis.com/auth/presentations"]
        self.service = self._get_slides_service()
        
        # Standard 16:9 presentation dimensions in EMU
        self.SLIDE_WIDTH = 9144000
        self.SLIDE_HEIGHT = 5143500
    
    def _get_slides_service(self):
        """Initialize and return the Google Slides service."""
        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.scopes
                )
                creds = flow.run_local_server(port=8080)
            
            with open(self.token_file, "w") as token:
                token.write(creds.to_json())
        
        return build("slides", "v1", credentials=creds)
    
    def get_position_from_coordinates(self, x: float, y: float, width: float, height: float) -> Position:
        """Determine element position based on its coordinates."""
        # Convert to relative positions (0-1)
        x_center = (x + width/2) / self.SLIDE_WIDTH
        y_center = (y + height/2) / self.SLIDE_HEIGHT
        
        logger.debug(f"Position analysis for ({x}, {y}):")
        logger.debug(f"  - Relative center point: ({x_center:.2f}, {y_center:.2f})")
        
        # Define grid sections
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
        
        logger.debug(f"  - Grid position: {v_pos}_{h_pos}")
        
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
            logger.warning(f"Invalid position string: {position_str}, defaulting to CENTER")
            return Position.CENTER
    
    def get_elements(self) -> Dict[str, SlideElement]:
        """Get all elements from the current presentation."""
        presentation = self.service.presentations().get(
            presentationId=self.presentation_id
        ).execute()
        
        elements = {}
        for page_number, slide in enumerate(presentation.get('slides', []), 1):
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
                
                # Process text elements
                if 'shape' in element and 'text' in element['shape']:
                    text_content = ''
                    for text_element in element['shape']['text'].get('textElements', []):
                        if 'textRun' in text_element:
                            text_content += text_element['textRun'].get('content', '')
                    
                    if text_content.strip():
                        elements[element_id] = SlideElement(
                            object_id=element_id,
                            element_type=ElementType.TEXT,
                            content=text_content.strip(),
                            position=position,
                            size=size,
                            page_number=page_number
                        )
        
        return elements
    
    def update_element_text(self, object_id: str, new_text: str) -> bool:
        """Update the text content of an element."""
        try:
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
            
            self.service.presentations().batchUpdate(
                presentationId=self.presentation_id,
                body={"requests": requests}
            ).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error updating text: {str(e)}")
            return False
    
    def resize_element(self, object_id: str, scale_factor: float) -> bool:
        """Resize an element by a scale factor."""
        try:
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
            
            self.service.presentations().batchUpdate(
                presentationId=self.presentation_id,
                body={"requests": requests}
            ).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error resizing element: {str(e)}")
            return False
    
    def process_command(self, command: str) -> str:
        """Process a voice command and return the result."""
        from ..nlp.parser import CommandParser  # Import here to avoid circular dependency
        
        parser = CommandParser()
        cmd = parser.parse(command)
        
        if not cmd.action_type:
            return "I couldn't understand what you want me to do. Try being more specific."
        
        elements = self.get_elements()
        if not elements:
            return "I don't see any elements in the presentation."
        
        # Find target element
        target_element = None
        if cmd.target_position:
            for element in elements.values():
                pos = self.get_position_from_coordinates(
                    element.position['x'],
                    element.position['y'],
                    element.size['width'],
                    element.size['height']
                )
                if pos == cmd.target_position:
                    target_element = element
                    break
        
        if not target_element:
            # Default to first element or look for title
            if "title" in command.lower():
                for element in elements.values():
                    if "title" in element.content.lower():
                        target_element = element
                        break
            if not target_element:
                target_element = next(iter(elements.values()))
        
        # Execute the command
        try:
            if cmd.action_type == ActionType.RESIZE:
                scale = cmd.parameters.get('scale_factor', 1.2)
                if self.resize_element(target_element.object_id, scale):
                    return f"Done! I've made the text {'bigger' if scale > 1 else 'smaller'}"
            
            elif cmd.action_type == ActionType.CHANGE_TEXT:
                new_text = cmd.parameters.get('new_text', '')
                if self.update_element_text(target_element.object_id, new_text):
                    return "Done! I've updated the text"
            
        except Exception as e:
            logger.exception("Error executing command")
            return f"Sorry, I ran into an error: {str(e)}"
        
        return "I couldn't complete that action. Please try again." 