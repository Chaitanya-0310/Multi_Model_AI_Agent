import os
import json
import logging
import pickle
from typing import Optional, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

logger = logging.getLogger("google_utils")

SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive.file',
]

TOKEN_PATH = 'token.pickle'


def get_google_credentials():
    """
    Load Google credentials from available sources (priority order):
      1. Saved token.pickle (reuse + refresh)
      2. GOOGLE_SERVICE_ACCOUNT_INFO env var
      3. GDRIVE_CLIENT_ID + GDRIVE_CLIENT_SECRET env vars  ← works with your .env
      4. credentials.json file in project root
    Returns None with a clear error log if nothing is available.
    """
    creds = None

    # 1. Saved token
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)

    # Refresh expired token
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            return creds
        except Exception as e:
            logger.warning(f"Token refresh failed: {e}. Re-authenticating...")
            creds = None

    if creds and creds.valid:
        return creds

    # 2. Service account from env var
    service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT_INFO")
    if service_account_info:
        try:
            info = json.loads(service_account_info)
            return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception as e:
            logger.warning(f"Service account credentials failed: {e}")

    # 3. OAuth from GDRIVE_CLIENT_ID + GDRIVE_CLIENT_SECRET env vars
    client_id = os.environ.get("GDRIVE_CLIENT_ID", "")
    client_secret = os.environ.get("GDRIVE_CLIENT_SECRET", "")
    if client_id and client_secret and not client_id.startswith("your_"):
        try:
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)
            _save_token(creds)
            logger.info("OAuth completed via GDRIVE_CLIENT_ID / GDRIVE_CLIENT_SECRET")
            return creds
        except Exception as e:
            logger.warning(f"OAuth from env vars failed: {e}")

    # 4. credentials.json file
    if os.path.exists('credentials.json'):
        try:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            _save_token(creds)
            return creds
        except Exception as e:
            logger.warning(f"credentials.json OAuth failed: {e}")

    logger.error(
        "No Google credentials found. To enable Google Docs publishing:\n"
        "  Option A: Set GDRIVE_CLIENT_ID and GDRIVE_CLIENT_SECRET in your .env file\n"
        "            (Create an OAuth2 Desktop App credential in Google Cloud Console)\n"
        "  Option B: Place credentials.json in the project root\n"
        "  Option C: Set GOOGLE_SERVICE_ACCOUNT_INFO env var (service account JSON)"
    )
    return None


def _save_token(creds):
    """Persist OAuth token to disk (skips service account credentials)."""
    if not isinstance(creds, service_account.Credentials):
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)


def get_google_service(service_name: str, version: str):
    """Build and return a Google API service client, or None if credentials unavailable."""
    creds = get_google_credentials()
    if not creds:
        return None
    return build(service_name, version, credentials=creds)


def publish_draft_to_gdoc(title: str, content: str) -> Tuple[str, str]:
    """
    Publish a draft to Google Docs.

    Tries MCP first (if mcp_config.json is present and GDRIVE credentials are set),
    then falls back to the direct Google Docs API.

    Returns:
        (doc_id, doc_url) — returns mock values if credentials are unavailable.
    """
    return create_doc(title, content, use_mcp=True)


def get_publish_status() -> dict:
    """
    Check which publishing path is available.
    Returns a dict with 'mcp_available', 'api_available', and 'message'.
    """
    status = {"mcp_available": False, "api_available": False, "message": ""}

    # Check MCP availability
    client_id = os.environ.get("GDRIVE_CLIENT_ID", "")
    client_secret = os.environ.get("GDRIVE_CLIENT_SECRET", "")
    mcp_config_exists = os.path.exists("mcp_config.json")
    if mcp_config_exists and client_id and not client_id.startswith("your_"):
        status["mcp_available"] = True

    # Check direct API availability
    if os.path.exists(TOKEN_PATH):
        status["api_available"] = True
    elif os.environ.get("GOOGLE_SERVICE_ACCOUNT_INFO"):
        status["api_available"] = True
    elif client_id and client_secret and not client_id.startswith("your_"):
        status["api_available"] = True  # Can OAuth
    elif os.path.exists("credentials.json"):
        status["api_available"] = True  # Can OAuth

    if status["mcp_available"]:
        status["message"] = "MCP (Google Drive) + Direct API available"
    elif status["api_available"]:
        status["message"] = "Direct Google Docs API available (MCP not configured)"
    else:
        status["message"] = (
            "No Google credentials configured. Publishing will save mock URLs. "
            "To enable real publishing: set GDRIVE_CLIENT_ID + GDRIVE_CLIENT_SECRET in .env, "
            "or place credentials.json in the project root."
        )

    return status


def create_doc(title: str, content: str, use_mcp: bool = True) -> Tuple[str, str]:
    """
    Create a Google Doc and return (doc_id, doc_url).

    Tries MCP first (if use_mcp=True), falls back to direct Google Docs API.
    Returns mock values when no credentials are configured.
    """
    if use_mcp:
        try:
            from src.mcp_client import get_gdrive_client
            mcp_client = get_gdrive_client()
            if mcp_client and mcp_client.start_server():
                result = mcp_client.create_google_doc(title, content)
                mcp_client.stop_server()
                if result:
                    logger.info(f"Created doc via MCP: {result[1]}")
                    return result
                logger.warning("MCP returned None, falling back to API")
            else:
                logger.warning("MCP unavailable, falling back to API")
        except Exception as e:
            logger.warning(f"MCP failed: {e}, falling back to Google API")

    service = get_google_service('docs', 'v1')
    if not service:
        mock_id = f"mock_{title[:20].replace(' ', '_')}"
        mock_url = f"https://docs.google.com/document/d/{mock_id}"
        logger.warning(f"No credentials — returning mock Doc URL: {mock_url}")
        return mock_id, mock_url

    doc = service.documents().create(body={'title': title}).execute()
    doc_id = doc.get('documentId')

    service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': [{'insertText': {'location': {'index': 1}, 'text': content}}]}
    ).execute()

    doc_url = f"https://docs.google.com/document/d/{doc_id}"
    logger.info(f"Created Google Doc: {doc_url}")
    return doc_id, doc_url


def add_calendar_event(summary: str, start_time: str, description: Optional[str] = None) -> str:
    """Add a publishing event to Google Calendar. Returns event ID or mock."""
    service = get_google_service('calendar', 'v3')
    if not service:
        return "mock_event_id"

    event = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_time, 'timeZone': 'UTC'},
        'end': {'dateTime': start_time, 'timeZone': 'UTC'},
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    return event.get('id')
