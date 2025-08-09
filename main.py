import os
from datetime import date, datetime, timezone, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from google_auth_oauthlib.flow import Flow
import requests
from calendar import monthrange
from collections import defaultdict
import json
import concurrent.futures
from typing import Dict, List, Tuple
import time
from functools import lru_cache
from pydantic import BaseModel

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Simple in-memory cache for user data (cache for 5 minutes)
user_cache = {}
CACHE_DURATION = 300  # 5 minutes in seconds

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# Extract the API key from the environment variable
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK", "")
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

class TransportData(BaseModel):
    bus: float
    car: float
    bike: float
    cycle: float
    walking: float
    totalDistance: float
    totalEmission: float

def fetch_monthly_data(access_token: str, year: int, month: int) -> Dict:
    """Fetch monthly data for a specific year and month with optimized API calls"""
    headers = {"Authorization": f"Bearer {access_token}"}
    inbox_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    
    # Get first and last day of the month
    first_day = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day_num = monthrange(year, month)[1]
    last_day = datetime(year, month, last_day_num, 23, 59, 59, tzinfo=timezone.utc)
    first_day_unix = int(first_day.timestamp())
    last_day_unix = int(last_day.timestamp())
    
    # Use larger maxResults to reduce API calls
    max_results = 1000  # Increased from 500
    
    # Fetch received emails for this month
    received_query = f"in:inbox after:{first_day_unix} before:{last_day_unix}"
    received_count = 0
    next_page_token = None
    page_count = 0
    max_pages = 3  # Limit pages to prevent excessive API calls
    
    while page_count < max_pages:
        params = {"q": received_query, "maxResults": max_results}
        if next_page_token:
            params["pageToken"] = next_page_token
        
        try:
            inbox_response = requests.get(inbox_url, headers=headers, params=params, timeout=10)
            if inbox_response.status_code != 200:
                break
            inbox_json = inbox_response.json()
            messages = inbox_json.get("messages", [])
            received_count += len(messages)
            next_page_token = inbox_json.get("nextPageToken")
            page_count += 1
            if not next_page_token:
                break
        except requests.exceptions.Timeout:
            print(f"Timeout fetching received emails for {year}-{month}")
            break
        except Exception as e:
            print(f"Error fetching received emails for {year}-{month}: {e}")
            break
    
    # Fetch sent emails for this month
    sent_query = f"in:sent after:{first_day_unix} before:{last_day_unix}"
    sent_count = 0
    next_page_token = None
    page_count = 0
    
    while page_count < max_pages:
        params = {"q": sent_query, "maxResults": max_results}
        if next_page_token:
            params["pageToken"] = next_page_token
        
        try:
            sent_response = requests.get(inbox_url, headers=headers, params=params, timeout=10)
            if sent_response.status_code != 200:
                break
            sent_json = sent_response.json()
            messages = sent_json.get("messages", [])
            sent_count += len(messages)
            next_page_token = sent_json.get("nextPageToken")
            page_count += 1
            if not next_page_token:
                break
        except requests.exceptions.Timeout:
            print(f"Timeout fetching sent emails for {year}-{month}")
            break
        except Exception as e:
            print(f"Error fetching sent emails for {year}-{month}: {e}")
            break
    
    # Format month name
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    month_name = month_names[month - 1]
    
    return {
        "month": f"{month_name} {year}",
        "sent": sent_count,
        "received": received_count
    }

@lru_cache(maxsize=128)
def fetch_current_month_data(access_token: str) -> Tuple[int, int]:
    """Fetch current month received and sent email counts with caching"""
    headers = {"Authorization": f"Bearer {access_token}"}
    inbox_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    
    # Get current month stats
    now_utc = datetime.now(timezone.utc)
    first_day_utc = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    first_day_unix = int(first_day_utc.timestamp())
    
    # Use larger maxResults and timeout
    max_results = 1000
    max_pages = 5
    
    # Get received emails count
    received_query = f"in:inbox after:{first_day_unix}"
    total_received_count = 0
    next_page_token = None
    page_count = 0
    
    while page_count < max_pages:
        params = {"q": received_query, "maxResults": max_results}
        if next_page_token:
            params["pageToken"] = next_page_token
        
        try:
            inbox_response = requests.get(inbox_url, headers=headers, params=params, timeout=15)
            if inbox_response.status_code != 200:
                break
            inbox_json = inbox_response.json()
            messages = inbox_json.get("messages", [])
            total_received_count += len(messages)
            next_page_token = inbox_json.get("nextPageToken")
            page_count += 1
            if not next_page_token:
                break
        except requests.exceptions.Timeout:
            print("Timeout fetching current month received emails")
            break
        except Exception as e:
            print(f"Error fetching current month received emails: {e}")
            break
    
    # Get sent emails count
    sent_query = f"in:sent after:{first_day_unix}"
    total_sent_count = 0
    next_page_token = None
    page_count = 0
    
    while page_count < max_pages:
        params = {"q": sent_query, "maxResults": max_results}
        if next_page_token:
            params["pageToken"] = next_page_token
        
        try:
            sent_response = requests.get(inbox_url, headers=headers, params=params, timeout=15)
            if sent_response.status_code != 200:
                break
            sent_json = sent_response.json()
            messages = sent_json.get("messages", [])
            total_sent_count += len(messages)
            next_page_token = sent_json.get("nextPageToken")
            page_count += 1
            if not next_page_token:
                break
        except requests.exceptions.Timeout:
            print("Timeout fetching current month sent emails")
            break
        except Exception as e:
            print(f"Error fetching current month sent emails: {e}")
            break
    
    return total_received_count, total_sent_count

def get_user_data_from_token(access_token):
    """Get user data using stored access token with parallel processing and caching"""
    # Check cache first
    cache_key = f"{access_token[:20]}"  # Use first 20 chars of token as cache key
    current_time = time.time()
    
    if cache_key in user_cache:
        cached_data, cache_time = user_cache[cache_key]
        if current_time - cache_time < CACHE_DURATION:
            print("Using cached data")
            return cached_data
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    try:
        userinfo_response = requests.get(userinfo_url, headers=headers, timeout=10)
        if userinfo_response.status_code != 200:
            return None
        
        userinfo_json = userinfo_response.json()
        user_email = userinfo_json.get("email")
        user_name = userinfo_json.get("name", "Unknown")
    except Exception as e:
        print(f"Error fetching user info: {e}")
        return None
    
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
    
    # Get current month data
    total_received_count, total_sent_count = fetch_current_month_data(access_token)
    
    # Get monthly stats for last 12 months using parallel processing
    monthly_stats = []
    current_date = datetime.now(timezone.utc)
    
    # Prepare list of (year, month) tuples for parallel processing
    month_tasks = []
    for i in range(11, -1, -1):  # 11 to 0 (12 months backwards)
        target_date = current_date.replace(day=1) - timedelta(days=i*30)
        year = target_date.year
        month = target_date.month
        month_tasks.append((year, month))
    
    # Use ThreadPoolExecutor for parallel processing with more workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        # Submit all tasks
        future_to_month = {
            executor.submit(fetch_monthly_data, access_token, year, month): (year, month)
            for year, month in month_tasks
        }
        
        # Collect results as they complete
        results = []
        for future in concurrent.futures.as_completed(future_to_month):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Error fetching data for month: {e}")
                # Add empty result for failed month
                year, month = future_to_month[future]
                month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                month_name = month_names[month - 1]
                results.append({
                    "month": f"{month_name} {year}",
                    "sent": 0,
                    "received": 0
                })
    
    # Sort results by chronological order (they might come back in different order due to parallel processing)
    # Create a mapping for proper chronological sorting
    month_order = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    
    def sort_key(item):
        month_name = item["month"].split()[0]  # Extract month name (e.g., "Jan")
        year = int(item["month"].split()[1])   # Extract year (e.g., "2024")
        return (year, month_order[month_name])
    
    monthly_stats = sorted(results, key=sort_key)
    
    result_data = {
        "user_name": user_name,
        "user_email": user_email,
        "received_count": total_received_count,
        "sent_count": total_sent_count,
        "drive_storage_gb": drive_storage_gb,
        "monthly_stats": monthly_stats
    }
    
    # Cache the result
    user_cache[cache_key] = (result_data, current_time)
    
    return result_data

def get_ai_transportation_tips() -> List[str]:
    """Generate AI-powered transportation tips using OpenRouter API"""
    if not DEEPSEEK_API_KEY:
        # Return empty list if no API key
        return []
    
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "ZeroPrint Calculator"
        }
        
        prompt = """Generate 5 practical and actionable green transportation tips for reducing carbon emissions. 
        Each tip should be:
        - Specific and actionable
        - Focused on reducing CO2 emissions
        - Include a brief explanation of the environmental impact
        - Start with a checkmark emoji (✅)
        - Be concise (1-2 sentences max)
        
        Format each tip as a single line starting with ✅. Return only the 5 tips, one per line."""
        
        data = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # Parse the tips from the response
            tips = []
            for line in content.strip().split('\n'):
                line = line.strip()
                if line.startswith('✅') and len(line) > 1:
                    tips.append(line)
            
            # Return up to 5 tips
            return tips[:5]
        
    except Exception as e:
        print(f"Error generating AI tips: {e}")
    
    # Return empty list if API fails
    return []

def get_tailored_transportation_tips(transport_data: TransportData) -> List[str]:
    """Generate AI-powered tailored transportation tips based on user's transport data"""
    if not DEEPSEEK_API_KEY:
        # Return empty list if no API key
        return []
    
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "ZeroPrint Calculator"
        }
        
        # Calculate key metrics for personalization
        car_emission = transport_data.car * 0.21
        bus_emission = transport_data.bus * 0.12
        bike_emission = transport_data.bike * 0.075
        zero_emission_distance = transport_data.cycle + transport_data.walking
        total_distance = transport_data.totalDistance
        zero_emission_percentage = (zero_emission_distance / total_distance * 100) if total_distance > 0 else 0
        
        # Create highly personalized prompt
        prompt = f"""You are a friendly, encouraging sustainability coach. Analyze this user's transportation habits and give them 5 highly personalized tips.

USER'S TRANSPORT DATA:
- Car: {transport_data.car} km ({car_emission:.1f} kg CO2)
- Bus: {transport_data.bus} km ({bus_emission:.1f} kg CO2) 
- Bike: {transport_data.bike} km ({bike_emission:.1f} kg CO2)
- Cycling: {transport_data.cycle} km (0 kg CO2)
- Walking: {transport_data.walking} km (0 kg CO2)
- Total distance: {total_distance} km
- Total CO2: {transport_data.totalEmission:.1f} kg
- Zero-emission percentage: {zero_emission_percentage:.1f}%

PERSONALIZATION RULES:
1. If car usage is high (>50km), suggest specific alternatives like "Since you drove {transport_data.car}km this week, try replacing 20km with cycling to save {transport_data.car * 0.21 * 0.5:.1f}kg CO2"
2. If zero-emission percentage is high (>60%), praise them: "Amazing! {zero_emission_percentage:.1f}% of your travel is zero-emission!"
3. If total emission is high (>10kg), express concern: "Your {transport_data.totalEmission:.1f}kg CO2 is quite high. Here's how to reduce it..."
4. Use their actual numbers in suggestions: "Your {transport_data.car}km car trips could be reduced by..."
5. If they walk/cycle a lot, encourage them: "Great job with {zero_emission_distance}km of zero-emission travel!"

TONE: Be encouraging, specific, and use their actual numbers. Make it feel like you're talking directly to them about their specific habits.

Format each tip as a single line starting with ✅. Return only the 5 tips, one per line."""
        
        data = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.8,
            "max_tokens": 600
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # Parse the tips from the response
            tips = []
            for line in content.strip().split('\n'):
                line = line.strip()
                if line.startswith('✅') and len(line) > 1:
                    tips.append(line)
            
            # Return up to 5 tips
            return tips[:5]
        
    except Exception as e:
        print(f"Error generating tailored AI tips: {e}")
    
    # Return empty list if API fails
    return []

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

@app.get("/dashboard")
def dashboard(request: Request):
    # Check if user is logged in via cookie
    access_token = request.cookies.get("access_token")
    
    if access_token:
        # User is logged in, get data from token
        user_data = get_user_data_from_token(access_token)
        if user_data:
            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                **user_data,
                "error": None
            })
    
    # User not logged in, redirect to home
    return RedirectResponse("/")

@app.get("/calculator")
def calculator(request: Request):
    # Check if user is logged in via cookie
    access_token = request.cookies.get("access_token")
    
    if access_token:
        # User is logged in, get data from token
        user_data = get_user_data_from_token(access_token)
        if user_data:
            return templates.TemplateResponse("calculator.html", {
                "request": request,
                **user_data,
                "ai_tips": [],  # Start with empty tips, will load asynchronously
                "error": None
            })
    
    # User not logged in, redirect to home
    return RedirectResponse("/")

@app.get("/api/ai-tips")
def get_ai_tips_api():
    """API endpoint to get AI tips asynchronously"""
    tips = get_ai_transportation_tips()
    return {"tips": tips}

@app.post("/api/tailored-tips")
def get_tailored_tips_api(transport_data: TransportData):
    """API endpoint to get tailored AI tips based on transport data"""
    tips = get_tailored_transportation_tips(transport_data)
    return {"tips": tips}

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
    
    # Create response with cookie and redirect to dashboard
    response = RedirectResponse("/dashboard")
    response.set_cookie(key="access_token", value=access_token, max_age=3600)  # 1 hour
    
    return response



@app.get("/logout")
def logout(request: Request):
    response = RedirectResponse("/")
    response.delete_cookie("access_token")
    return response