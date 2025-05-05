from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel

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

class ActionType(Enum):
    CHANGE_TEXT = "change_text"
    RESIZE = "resize"
    MOVE = "move"
    FORMAT = "format"

class SlideElement(BaseModel):
    object_id: str
    element_type: ElementType
    content: str
    position: Dict[str, float]
    size: Dict[str, float]
    page_number: int

class VoiceCommand(BaseModel):
    """Represents a processed voice command"""
    raw_text: str
    action_type: Optional[ActionType] = None
    target_position: Optional[Position] = None
    parameters: Dict[str, any] = {} 