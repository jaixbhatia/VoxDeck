"""
Google Slides API Utilities

This module provides utility functions for manipulating Google Slides presentations
programmatically. It includes functionality for resizing elements and images while
maintaining aspect ratios and proper positioning.

Example:
    ```python
    # Resize an image in a presentation
    resize_image(
        presentation_id="your_presentation_id",
        image_id="your_image_id",
        scale_factor=1.5  # Increase size by 50%
    )
    ```

Note:
    This module requires proper Google API authentication to be set up.
    See Google Slides API documentation for authentication setup.
"""

from typing import Dict, List, Optional
import logging
from googleapiclient.discovery import build
from google.oauth2 import service_account

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Google Slides API client
# Note: SLIDES should be initialized with proper credentials before use
SLIDES = None  # This should be initialized with proper credentials

def initialize_slides_api(credentials_path: str) -> None:
    """
    Initialize the Google Slides API client with credentials.
    
    Args:
        credentials_path: Path to the service account credentials JSON file
    """
    global SLIDES
    try:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/presentations']
        )
        SLIDES = build('slides', 'v1', credentials=credentials)
        logger.info("Successfully initialized Google Slides API client")
    except Exception as e:
        logger.error(f"Failed to initialize Google Slides API: {e}")
        raise

def get_element_by_id(presentation_id: str, element_id: str) -> Optional[Dict]:
    """
    Retrieve an element from a presentation by its ID.
    
    Args:
        presentation_id: The ID of the presentation
        element_id: The ID of the element to retrieve
        
    Returns:
        Optional[Dict]: The element if found, None otherwise
    """
    try:
        presentation = SLIDES.presentations().get(
            presentationId=presentation_id
        ).execute()
        
        for slide in presentation.get('slides', []):
            for element in slide.get('pageElements', []):
                if element['objectId'] == element_id:
                    return element
        return None
    except Exception as e:
        logger.error(f"Error retrieving element: {e}")
        return None

def resize_element(presentation_id: str, element_id: str, scale_factor: float) -> Optional[Dict]:
    """
    Resize an element by a scale factor while maintaining its aspect ratio and center position.
    
    Args:
        presentation_id: The ID of the presentation
        element_id: The ID of the element to resize
        scale_factor: Factor to scale by (>1 for increase, <1 for decrease)
        
    Returns:
        Optional[Dict]: The API response if successful, None otherwise
        
    Raises:
        ValueError: If scale_factor is not positive
        Exception: If the API request fails
    """
    if scale_factor <= 0:
        raise ValueError("Scale factor must be positive")
        
    try:
        # Get the current element
        element = get_element_by_id(presentation_id, element_id)
        if not element:
            logger.error(f"Could not find element with ID {element_id}")
            return None

        # Get current size and position
        current_height = element['size']['height']['magnitude']
        current_width = element['size']['width']['magnitude']
        current_x = element['transform']['translateX']
        current_y = element['transform']['translateY']
        
        # Calculate position adjustment to keep element centered
        x_adjust = (current_width - (current_width * scale_factor)) / 2
        y_adjust = (current_height - (current_height * scale_factor)) / 2
        
        # Create the update request
        requests = [{
            'updatePageElementTransform': {
                'objectId': element_id,
                'transform': {
                    'scaleX': scale_factor,
                    'scaleY': scale_factor,
                    'translateX': current_x + x_adjust,
                    'translateY': current_y + y_adjust,
                    'unit': 'EMU'
                },
                'applyMode': 'ABSOLUTE'
            }
        }]
        
        # Execute the update
        response = SLIDES.presentations().batchUpdate(
            presentationId=presentation_id,
            body={'requests': requests}
        ).execute()
        
        logger.info(f"Successfully resized element by factor {scale_factor}")
        return response
        
    except Exception as e:
        logger.error(f"Error resizing element: {e}")
        raise

def is_image_element(element: Dict) -> bool:
    """
    Check if an element is an image.
    
    Args:
        element: The element to check
        
    Returns:
        bool: True if the element is an image, False otherwise
    """
    return 'image' in element or (
        'shape' in element and 
        element['shape'].get('shapeType') in ['RECTANGLE', 'PICTURE']
    )

def get_image_elements(presentation_id: str, page_id: str) -> List[Dict]:
    """
    Get all image elements on a specific page of a presentation.
    
    Args:
        presentation_id: The ID of the presentation
        page_id: The ID of the page to search
        
    Returns:
        List[Dict]: List of image elements found on the page
    """
    try:
        presentation = SLIDES.presentations().get(
            presentationId=presentation_id
        ).execute()
        
        # Find the specified page
        page = next(
            (p for p in presentation.get('slides', []) if p['objectId'] == page_id),
            None
        )
                
        if not page:
            logger.error(f"Could not find page with ID {page_id}")
            return []
            
        # Get all image elements on the page
        return [
            element for element in page.get('pageElements', [])
            if is_image_element(element)
        ]
        
    except Exception as e:
        logger.error(f"Error getting image elements: {e}")
        return []

def resize_image(presentation_id: str, image_id: str, scale_factor: float) -> Optional[Dict]:
    """
    Resize an image by a scale factor while maintaining its aspect ratio.
    
    Args:
        presentation_id: The ID of the presentation
        image_id: The ID of the image to resize
        scale_factor: Factor to scale by (>1 for increase, <1 for decrease)
        
    Returns:
        Optional[Dict]: The API response if successful, None otherwise
        
    Raises:
        ValueError: If scale_factor is not positive
        Exception: If the API request fails or element is not an image
    """
    if scale_factor <= 0:
        raise ValueError("Scale factor must be positive")
        
    try:
        # Get the current image
        image = get_element_by_id(presentation_id, image_id)
        if not image or not is_image_element(image):
            logger.error(f"Could not find image with ID {image_id}")
            return None
            
        # Create the update request
        requests = [{
            'updatePageElementTransform': {
                'objectId': image_id,
                'transform': {
                    'scaleX': scale_factor,
                    'scaleY': scale_factor,
                    'unit': 'EMU'
                },
                'applyMode': 'RELATIVE'
            }
        }]
        
        # Execute the update
        response = SLIDES.presentations().batchUpdate(
            presentationId=presentation_id,
            body={'requests': requests}
        ).execute()
        
        logger.info(f"Successfully resized image by factor {scale_factor}")
        return response
        
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        raise 