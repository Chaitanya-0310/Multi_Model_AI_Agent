import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# Scopes for Google Docs and Calendar
SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/calendar'
]

def get_google_service(service_name, version):
    """
    Creates a Google API service.
    In a real environment, this would handle OAuth2 or Service Account.
    For this task, we will try to load from environment or local files.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Check for service account info in environment
            service_account_info = os.environ.get("GOOGLE_SERVICE_ACCOUNT_INFO")
            if service_account_info:
                info = json.loads(service_account_info)
                creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            elif os.path.exists('credentials.json'):
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            else:
                # Fallback or Mock for this environment
                print("Warning: No Google credentials found. Using mock service if applicable.")
                return None

        # Save the credentials for the next run
        if not isinstance(creds, service_account.Credentials) and os.path.exists('credentials.json'):
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

    return build(service_name, version, credentials=creds)

def create_doc(title, content, use_mcp=True):
    """Creates a Google Doc and returns the document ID and URL.
    
    Args:
        title: Document title
        content: Document content
        use_mcp: Whether to try MCP first (default: True)
        
    Returns:
        Tuple of (doc_id, doc_url)
    """
    # Try MCP first if enabled
    if use_mcp:
        try:
            from src.mcp_client import get_gdrive_client
            import logging
            logger = logging.getLogger("google_utils")
            
            logger.info("Attempting to create document via MCP...")
            mcp_client = get_gdrive_client()
            
            if mcp_client:
                if mcp_client.start_server():
                    result = mcp_client.create_google_doc(title, content)
                    mcp_client.stop_server()
                    
                    if result:
                        logger.info(f"Successfully created document via MCP: {result[1]}")
                        return result
                    else:
                        logger.warning("MCP document creation returned None, falling back to API")
                else:
                    logger.warning("MCP server failed to start, falling back to API")
            else:
                logger.warning("MCP client not available, falling back to API")
        except Exception as e:
            import logging
            logger = logging.getLogger("google_utils")
            logger.warning(f"MCP creation failed: {e}, falling back to Google API")
    
    # Fallback to direct Google API
    service = get_google_service('docs', 'v1')
    if not service:
        return "mock_doc_id", "https://docs.google.com/document/d/mock_doc_id"
        
    doc = service.documents().create(body={'title': title}).execute()
    doc_id = doc.get('documentId')
    
    # Add content to the document
    requests = [
        {
            'insertText': {
                'location': {
                    'index': 1,
                },
                'text': content
            }
        }
    ]
    service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
    
    return doc_id, f"https://docs.google.com/document/d/{doc_id}"

def add_calendar_event(summary, start_time, description=None):
    """Adds an event to Google Calendar."""
    service = get_google_service('calendar', 'v3')
    if not service:
        return "mock_event_id"
        
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': start_time, # Simple: same start and end for a publish marker
            'timeZone': 'UTC',
        },
    }
    
    event = service.events().insert(calendarId='primary', body=event).execute()
    return event.get('id')
