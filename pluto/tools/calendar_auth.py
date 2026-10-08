import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# This scope allows reading AND writing to the calendar.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

CREDENTIALS_FILE = "credentials/google_credentials.json"
TOKEN_FILE = "credentials/calendar_token.json"

def get_calendar_service():
    """Authenticates with Google Calendar and returns the service object."""
    creds = None
    
    # 1. Check if we already have a saved token
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # 2. If there are no valid credentials, let the user log in
    if not creds or not creds.valid:
        
        # 3. If the token is expired but can be refreshed, refresh it!
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            
        # 4. Otherwise, trigger the browser login flow
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"Error: Could not find {CREDENTIALS_FILE}")
                return None
                
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)
            
        # 5. Save the new credentials to the token file for next time
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    # 6. Build and return the Calendar service
    try:
        service = build("calendar", "v3", credentials=creds)
        return service
    except Exception as e:
        print(f"Error building calendar service: {e}")
        return None

if __name__ == "__main__":
    service = get_calendar_service()
    if service:
        print("Calendar service authenticated successfully!")
