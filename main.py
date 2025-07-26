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
    return RedirectResponse(auth_url)

@app.get("/callback")
def callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return RedirectResponse("/")

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    try:
        flow.fetch_token(code=code)
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "received_count": None,
            "sent_count": None,
            "error": f"Error fetching token: {e}"
        })

    creds = flow.credentials
    headers = {"Authorization": f"Bearer {creds.token}"}

    # Fetch user's email address
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    userinfo_response = requests.get(userinfo_url, headers=headers)
    userinfo_json = userinfo_response.json()
    user_email = userinfo_json.get("email")

    # Use UTC for current month calculation
    now_utc = datetime.now(timezone.utc)
    first_day_utc = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    first_day_unix = int(first_day_utc.timestamp())

    inbox_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

    # Paginate through all received emails in inbox since first day of month
    received_query = f"in:inbox after:{first_day_unix}"
    total_received_count = 0
    next_page_token = None
    while True:
        params = {
            "q": received_query,
            "maxResults": 500
        }
        if next_page_token:
            params["pageToken"] = next_page_token
        inbox_response = requests.get(inbox_url, headers=headers, params=params)
        if inbox_response.status_code != 200:
            break
        inbox_json = inbox_response.json()
        messages = inbox_json.get("messages", [])
        total_received_count += len(messages)
        next_page_token = inbox_json.get("nextPageToken")
        if not next_page_token:
            break

    # Paginate through all sent emails since first day of month
    sent_query = f"in:sent after:{first_day_unix}"
    total_sent_count = 0
    next_page_token = None
    while True:
        params = {
            "q": sent_query,
            "maxResults": 500
        }
        if next_page_token:
            params["pageToken"] = next_page_token
        sent_response = requests.get(inbox_url, headers=headers, params=params)
        if sent_response.status_code != 200:
            break
        sent_json = sent_response.json()
        messages = sent_json.get("messages", [])
        total_sent_count += len(messages)
        next_page_token = sent_json.get("nextPageToken")
        if not next_page_token:
            break

    return templates.TemplateResponse("index.html", {
        "request": request,
        "received_count": total_received_count,
        "sent_count": total_sent_count,
        "error": None
    })