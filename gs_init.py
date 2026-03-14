import gspread
from google.oauth2.service_account import Credentials
import json
import base64
from dotenv import load_dotenv
import os

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

GOOGLE_CREDENTIALS_B64 = os.getenv("GOOGLE_CREDENTIALS_B64")
if GOOGLE_CREDENTIALS_B64:
    creds_json = json.loads(base64.b64decode(GOOGLE_CREDENTIALS_B64))
    creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
else:
    creds = Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_FILE"), scopes=SCOPES
    )

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
gc = gspread.authorize(creds)
spreadsheet = gc.open_by_key(SPREADSHEET_ID)