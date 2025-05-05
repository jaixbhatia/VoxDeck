import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

# === Load env vars ===
load_dotenv()
PRESENTATION_ID = os.getenv("PRESENTATION_ID")
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS")
TOKEN_FILE = "token.json"
OBJECT_ID = "g354be6996ac_0_121"
NEW_TEXT = "Meet the VoxDeck Team 🚀"

SCOPES = ["https://www.googleapis.com/auth/presentations"]

from google.oauth2.credentials import Credentials

# === Auth with token caching ===
creds = None
if os.path.exists(TOKEN_FILE):
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=8080)
    with open(TOKEN_FILE, "w") as token:
        token.write(creds.to_json())

# === Google Slides client ===
service = build("slides", "v1", credentials=creds)

# === Replace text content ===
requests = [
    {
        "deleteText": {
            "objectId": OBJECT_ID,
            "textRange": {"type": "ALL"}
        }
    },
    {
        "insertText": {
            "objectId": OBJECT_ID,
            "insertionIndex": 0,
            "text": NEW_TEXT
        }
    }
]

res = service.presentations().batchUpdate(
    presentationId=PRESENTATION_ID,
    body={"requests": requests}
).execute()

print(f"✅ Replaced text for {OBJECT_ID}: {NEW_TEXT}")