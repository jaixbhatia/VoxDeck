import openai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# === CONFIG ===
openai.api_key = "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"  # Your OpenAI key
PRESENTATION_ID = "1j9xJES2HGvNROFszMGE3lMK6sUvSVDkgaXxmfgmyI-s"  # Your test deck
OBJECT_ID = "g123456abc_0_0"  # shape ID from a textbox on the slide

# === AUTH GOOGLE ===
SCOPES = ['https://www.googleapis.com/auth/presentations']
flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=8080)
service = build('slides', 'v1', credentials=creds)

# === STEP 1: NLP → GPT FUNCTION ===
user_command = "Make this text bold and blue"
response = openai.ChatCompletion.create(
  model="gpt-4-0613",
  messages=[{"role": "user", "content": user_command}],
  functions=[{
      "name": "update_text_style",
      "parameters": {
          "type": "object",
          "properties": {
              "objectId": {"type": "string"},
              "bold": {"type": "boolean"},
              "color": {
                  "type": "object",
                  "properties": {
                      "red": {"type": "number"},
                      "green": {"type": "number"},
                      "blue": {"type": "number"},
                  }
              }
          },
          "required": ["objectId"]
      }
  }],
  function_call="auto"
)

params = response.choices[0]["message"]["function_call"]["arguments"]

import json
args = json.loads(params)

# === STEP 2: CALL GOOGLE SLIDES API ===
requests = [{
    "updateTextStyle": {
        "objectId": args["objectId"],
        "style": {
            "bold": args.get("bold", True),
            "foregroundColor": {
                "opaqueColor": {
                    "rgbColor": args["color"]
                }
            }
        },
        "fields": "bold,foregroundColor"
    }
}]

res = service.presentations().batchUpdate(
    presentationId=PRESENTATION_ID, body={"requests": requests}
).execute()

print("Edit applied:", res)