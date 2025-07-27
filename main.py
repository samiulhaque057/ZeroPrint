import os
from datetime import date, datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from google_auth_oauthlib.flow import Flow
import requests
from calendar import monthrange
from collections import defaultdict
import json

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
    "https://www.googleapis.com/auth/drive.readonly",
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

def get_user_data_from_token(access_token):
    """Get user data using stored access token"""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    userinfo_response = requests.get(userinfo_url, headers=headers)
    if userinfo_response.status_code != 200:
        return None
    
    userinfo_json = userinfo_response.json()
    user_email = userinfo_json.get("email")
    user_name = userinfo_json.get("name", "Unknown")
    
    # Get current month stats
    now_utc = datetime.now(timezone.utc)
    first_day_utc = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    first_day_unix = int(first_day_utc.timestamp())
    
    inbox_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    
    # Get received emails count
    received_query = f"in:inbox after:{first_day_unix}"
    total_received_count = 0
    next_page_token = None
    while True:
        params = {"q": received_query, "maxResults": 500}
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
    
    # Get sent emails count
    sent_query = f"in:sent after:{first_day_unix}"
    total_sent_count = 0
    next_page_token = None
    while True:
        params = {"q": sent_query, "maxResults": 500}
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
    
    # Get Drive storage
    drive_about_url = "https://www.googleapis.com/drive/v3/about"
    drive_about_params = {"fields": "storageQuota"}
    drive_about_response = requests.get(drive_about_url, headers=headers, params=drive_about_params)
    
    drive_storage_gb = 0
    if drive_about_response.status_code == 200:
        drive_about_json = drive_about_response.json()
        storage_quota = drive_about_json.get("storageQuota", {})
        usage_in_drive = storage_quota.get("usageInDrive", "0")
        try:
            drive_storage_gb = round(int(usage_in_drive) / (1024**3), 2)
        except Exception:
            drive_storage_gb = 0
    
    # Get monthly stats
    monthly_stats = []
    for year in [2024, 2025]:
        start_month = 1 if year == 2024 else 1
        end_month = 12 if year == 2024 else 6
        for month in range(start_month, end_month + 1):
            first_day = datetime(year, month, 1, tzinfo=timezone.utc)
            last_day_num = monthrange(year, month)[1]
            last_day = datetime(year, month, last_day_num, 23, 59, 59, tzinfo=timezone.utc)
            first_day_unix = int(first_day.timestamp())
            last_day_unix = int(last_day.timestamp())
            
            # Received
            received_query = f"in:inbox after:{first_day_unix} before:{last_day_unix}"
            received_count = 0
            next_page_token = None
            while True:
                params = {"q": received_query, "maxResults": 500}
                if next_page_token:
                    params["pageToken"] = next_page_token
                inbox_response = requests.get(inbox_url, headers=headers, params=params)
                if inbox_response.status_code != 200:
                    break
                inbox_json = inbox_response.json()
                messages = inbox_json.get("messages", [])
                received_count += len(messages)
                next_page_token = inbox_json.get("nextPageToken")
                if not next_page_token:
                    break
            
            # Sent
            sent_query = f"in:sent after:{first_day_unix} before:{last_day_unix}"
            sent_count = 0
            next_page_token = None
            while True:
                params = {"q": sent_query, "maxResults": 500}
                if next_page_token:
                    params["pageToken"] = next_page_token
                sent_response = requests.get(inbox_url, headers=headers, params=params)
                if sent_response.status_code != 200:
                    break
                sent_json = sent_response.json()
                messages = sent_json.get("messages", [])
                sent_count += len(messages)
                next_page_token = sent_json.get("nextPageToken")
                if not next_page_token:
                    break
            
            monthly_stats.append({
                "month": first_day.strftime("%Y-%m"),
                "sent": sent_count,
                "received": received_count
            })
    
    return {
        "user_name": user_name,
        "user_email": user_email,
        "received_count": total_received_count,
        "sent_count": total_sent_count,
        "drive_storage_gb": drive_storage_gb,
        "monthly_stats": monthly_stats
    }

@app.get("/")
def home(request: Request):
    # Check if user is logged in via cookie
    access_token = request.cookies.get("access_token")
    
    if access_token:
        # User is logged in, get data from token
        user_data = get_user_data_from_token(access_token)
        if user_data:
            return templates.TemplateResponse("index.html", {
                "request": request,
                **user_data,
                "error": None
            })
    
    # User not logged in
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user_name": None,
        "user_email": None,
        "received_count": None,
        "sent_count": None,
        "drive_storage_gb": None,
        "monthly_stats": [],
        "error": None
    })

@app.post("/")
def home_post(request: Request):
    return RedirectResponse("/")

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
            "user_name": None,
            "user_email": None,
            "received_count": None,
            "sent_count": None,
            "drive_storage_gb": None,
            "monthly_stats": [],
            "error": f"Error fetching token: {e}"
        })

    creds = flow.credentials
    access_token = creds.token
    
    # Get user data
    user_data = get_user_data_from_token(access_token)
    
    # Create response with cookie
    response = templates.TemplateResponse("index.html", {
        "request": request,
        **user_data,
        "error": None
    })
    
    # Set cookie with access token (in production, use secure cookies)
    response.set_cookie(key="access_token", value=access_token, max_age=3600)  # 1 hour
    
    return response



@app.get("/logout")
def logout(request: Request):
    response = RedirectResponse("/")
    response.delete_cookie("access_token")
    return response