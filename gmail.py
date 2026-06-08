import base64
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    creds = None
    # Check for existing authorized user credentials
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Use OAuth flow with client_secret.json to get new credentials
            flow = InstalledAppFlow.from_client_secrets_file(
                "client_secret.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the authorized user credentials for future use
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


# ==============================================================================
# EXTRACT PLAIN TEXT CONTENT (BODY)
# ==============================================================================
def get_plain_text_body(payload):
    """Recursively checks layers of the message payload for plain text."""
    # Case A: Content is found directly in this part's body
    if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
        return payload["body"]["data"]

    # Case B: The message is multipart, look through all sub-parts
    if "parts" in payload:
        for part in payload["parts"]:
            body_data = get_plain_text_body(part)
            if body_data:
                return body_data
    return None


# ==============================================================================
# REMOVE CONTENT AFTER SIGNING OFF
# ==============================================================================
def remove_signature(content):
    """Removes content after common email sign-off phrases."""
    sign_off_phrases = ["until next week"]
    content_lower = content.lower()
    for phrase in sign_off_phrases:
        if phrase in content_lower:
            index = content_lower.find(phrase)
            return content[:index].strip()
    return content.strip()


# Read latest 5 messages
service = get_gmail_service()
results = (
    service.users()
    .messages()
    .list(
        userId="me",
        maxResults=5,
        labelIds=["INBOX", "UNREAD"],
        q="from:james@jamesclear.com",
    )
    .execute()
)
messages = results.get("messages", [])

if messages:
    for msg in messages[-3:-2]:
        message = service.users().messages().get(userId="me", id=msg["id"]).execute()
        print(f"Snippet: {message['snippet']}")
        # ==============================================================================
        # EXTRACT DATE & TITLE (SUBJECT) FROM HEADERS
        # ==============================================================================
        headers = message.get("payload", {}).get("headers", [])

        email_date = "Unknown Date"
        email_title = "No Subject"

        for header in headers:
            if header["name"].lower() == "date":
                email_date = header["value"]
            elif header["name"].lower() == "subject":
                email_title = header["value"]

        # Fetch the raw base64 string
        raw_body_data = get_plain_text_body(message.get("payload", {}))

        if raw_body_data:
            # Google uses URL-safe base64 encoding for email bodies
            decoded_bytes = base64.urlsafe_b64decode(raw_body_data.encode("ASCII"))
            email_content = decoded_bytes.decode("utf-8", errors="ignore")
        else:
            # Fallback to the short preview snippet if no plain text part is found
            email_content = message.get("snippet", "")
        # Remove content after signing off
        cleaned_content = remove_signature(email_content)
        # ==============================================================================
        # DISPLAY OR READ OUT RESULTS
        # ==============================================================================
        print(f"Date: {email_date}")
        print(f"Title: {email_title}")
        print(f"Content: {cleaned_content}\n")
