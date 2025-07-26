import os
from datetime import date, datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from google_auth_oauthlib.flow import Flow
import requests

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

client_config = {
    "web": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT_URI]
    }
}

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "received_count": None,
        "sent_count": None,
        "error": None
    })

@app.get("/login")
def login():
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(prompt='select_account', include_granted_scopes='true')
    print(f"Redirecting to Google OAuth URL: {auth_url}")
    return RedirectResponse(auth_url)

@app.get("/callback")
def callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        print("No OAuth code received in callback.")
        return RedirectResponse("/")

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    try:
        flow.fetch_token(code=code)
    except Exception as e:
        print(f"Error fetching OAuth token: {e}")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "received_count": None,
            "sent_count": None,
            "error": f"Error fetching token: {e}"
        })

    creds = flow.credentials
    headers = {"Authorization": f"Bearer {creds.token}"}
    print(f"Access token acquired (truncated): {creds.token[:10]}...")

    # Fetch user's email address
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    userinfo_response = requests.get(userinfo_url, headers=headers)
    userinfo_json = userinfo_response.json()
    user_email = userinfo_json.get("email")
    print(f"User email: {user_email}")

    # Use UTC for current month calculation
    now_utc = datetime.now(timezone.utc)
    first_day_utc = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    first_day_unix = int(first_day_utc.timestamp())
    print(f"Counting emails from the first day of the current month (UTC, Unix timestamp): {first_day_unix}")

    inbox_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

    # Paginate through all received emails in inbox since first day of month
    received_query = f"in:inbox after:{first_day_unix}"
    total_received_count = 0
    next_page_token = None
    received_ids = []
    while True:
        params = {
            "q": received_query,
            "maxResults": 500
        }
        if next_page_token:
            params["pageToken"] = next_page_token
        inbox_response = requests.get(inbox_url, headers=headers, params=params)
        if inbox_response.status_code != 200:
            print(f"Failed to fetch received emails: HTTP {inbox_response.status_code}")
            break
        inbox_json = inbox_response.json()
        messages = inbox_json.get("messages", [])
        total_received_count += len(messages)
        received_ids.extend([msg['id'] for msg in messages])
        next_page_token = inbox_json.get("nextPageToken")
        if not next_page_token:
            break
    print(f"Total received email count: {total_received_count}")
    print(f"First 10 received message IDs: {received_ids[:10]}")
    # Fetch and print subject and sender for first 10 received messages
    for msg_id in received_ids[:10]:
        msg_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}"
        msg_response = requests.get(msg_url, headers=headers, params={"format": "metadata", "metadataHeaders": ["Subject", "From"]})
        if msg_response.status_code == 200:
            msg_json = msg_response.json()
            headers_list = msg_json.get("payload", {}).get("headers", [])
            subject = next((h["value"] for h in headers_list if h["name"] == "Subject"), "(No Subject)")
            sender = next((h["value"] for h in headers_list if h["name"] == "From"), "(No Sender)")
            print(f"Received message: Subject: {subject}, From: {sender}")
        else:
            print(f"Failed to fetch message {msg_id}: HTTP {msg_response.status_code}")

    # Sent emails query - all emails in sent since first day of month
    sent_query = f"in:sent after:{first_day_unix}"
    sent_params = {
        "q": sent_query,
        "maxResults": 10
    }
    print(f"Requesting sent emails with query: {sent_query}")
    sent_response = requests.get(inbox_url, headers=headers, params=sent_params)
    print(f"Sent emails HTTP status: {sent_response.status_code}")
    try:
        sent_json = sent_response.json()
        print(f"Sent emails full response JSON: {sent_json}")
        sent_ids = [msg['id'] for msg in sent_json.get('messages', [])][:10]
        print(f"First 10 sent message IDs: {sent_ids}")
    except Exception as e:
        print(f"Failed to parse sent emails JSON: {e}")
        sent_json = {}
        sent_ids = []

    sent_count = sent_json.get("resultSizeEstimate", 0)
    print(f"Sent email count: {sent_count}")

    return templates.TemplateResponse("index.html", {
        "request": request,
        "received_count": total_received_count,
        "sent_count": sent_count,
        "error": None
    })
