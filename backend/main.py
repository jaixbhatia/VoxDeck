from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os

# Add parent directory to path to import nlp_editor
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nlp_editor import process_text_request, authenticate_google_slides

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Google Slides authentication on startup
@app.on_event("startup")
async def startup_event():
    try:
        authenticate_google_slides()
        print("✅ Successfully authenticated with Google Slides")
    except Exception as e:
        print(f"❌ Failed to authenticate with Google Slides: {str(e)}")
        # Don't raise the exception here, let the app start anyway
        # Individual requests will handle auth errors

class TextRequest(BaseModel):
    text: str

@app.post("/process")
async def process_text(request: TextRequest):
    """Process the text using nlp_editor"""
    try:
        result = process_text_request(request.text)
        return {"result": result}
    except FileNotFoundError:
        # Try to authenticate again if token is missing
        try:
            authenticate_google_slides()
            # Retry the request after authentication
            result = process_text_request(request.text)
            return {"result": result}
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to authenticate with Google Slides: {str(e)}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing text: {str(e)}"
        ) 