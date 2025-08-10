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
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func

load_dotenv()

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./challenges.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    challenges = relationship("UserChallenge", back_populates="user")
    achievements = relationship("UserAchievement", back_populates="user")

class Challenge(Base):
    __tablename__ = "challenges"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    challenge_type = Column(String, nullable=False)  # 'individual', 'team', 'company'
    target_value = Column(Float)
    target_unit = Column(String)  # 'km', 'emails', 'days', etc.
    start_date = Column(DateTime, default=func.now())
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    points_reward = Column(Integer, default=100)
    badge_icon = Column(String, default="🏆")
    created_at = Column(DateTime, default=func.now())

class UserChallenge(Base):
    __tablename__ = "user_challenges"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    challenge_id = Column(Integer, ForeignKey("challenges.id"))
    current_progress = Column(Float, default=0.0)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime)
    joined_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="challenges")
    challenge = relationship("Challenge")

class UserAchievement(Base):
    __tablename__ = "user_achievements"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    achievement_type = Column(String, nullable=False)  # 'streak', 'badge', 'milestone'
    title = Column(String, nullable=False)
    description = Column(Text)
    icon = Column(String, default="🎖️")
    earned_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="achievements")

# Create tables
Base.metadata.create_all(bind=engine)

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
        
        # Create dynamic, varied prompts for personalization
        import random
        
        # Different coaching styles and tones
        coaching_styles = [
            "friendly sustainability coach",
            "eco-friendly travel advisor", 
            "green transportation expert",
            "climate-conscious mobility guide",
            "sustainable travel mentor",
            "environmental impact specialist",
            "carbon footprint consultant",
            "green mobility advocate",
            "eco-transportation guru",
            "sustainability travel buddy"
        ]
        
        # Varied approaches for different scenarios
        car_alternatives = [
            f"Consider replacing some of your {transport_data.car}km car trips with cycling to save {transport_data.car * 0.21 * 0.3:.1f}kg CO2",
            f"Your {transport_data.car}km car usage could be reduced by trying public transport for shorter trips",
            f"Think about carpooling for your {transport_data.car}km weekly car journeys to cut emissions",
            f"Your car trips of {transport_data.car}km could be partially replaced with walking for distances under 2km",
            f"Your {transport_data.car}km car travel could be optimized by combining errands into fewer trips",
            f"Consider electric vehicle options for your {transport_data.car}km weekly car usage",
            f"Your {transport_data.car}km car journeys might benefit from a hybrid approach with some walking/cycling"
        ]
        
        praise_messages = [
            f"Fantastic work! {zero_emission_percentage:.1f}% of your travel is already zero-emission!",
            f"You're crushing it! {zero_emission_percentage:.1f}% zero-emission travel is amazing!",
            f"Outstanding! You're already at {zero_emission_percentage:.1f}% zero-emission travel!",
            f"Impressive! {zero_emission_percentage:.1f}% of your journeys are emission-free!"
        ]
        
        concern_messages = [
            f"Your {transport_data.totalEmission:.1f}kg CO2 footprint could be reduced with some changes...",
            f"At {transport_data.totalEmission:.1f}kg CO2, there's room for improvement in your travel choices...",
            f"Your current {transport_data.totalEmission:.1f}kg CO2 emissions suggest some optimization opportunities...",
            f"With {transport_data.totalEmission:.1f}kg CO2, consider these eco-friendly alternatives..."
        ]
        
        encouragement_messages = [
            f"Keep up the great work with your {zero_emission_distance}km of zero-emission travel!",
            f"Your {zero_emission_distance}km of walking/cycling is making a real difference!",
            f"Amazing commitment to sustainable travel with {zero_emission_distance}km of zero-emission journeys!",
            f"Your {zero_emission_distance}km of eco-friendly travel is inspiring!"
        ]
        
        # Add seasonal and contextual variations
        from datetime import datetime
        current_month = datetime.now().month
        
        # Seasonal variations
        seasonal_context = ""
        if current_month in [12, 1, 2]:  # Winter
            seasonal_context = " (consider weather-appropriate alternatives)"
        elif current_month in [3, 4, 5]:  # Spring
            seasonal_context = " (perfect weather for outdoor activities)"
        elif current_month in [6, 7, 8]:  # Summer
            seasonal_context = " (great time for cycling and walking)"
        elif current_month in [9, 10, 11]:  # Fall
            seasonal_context = " (enjoy the beautiful weather while being eco-friendly)"
        
        # Additional contextual elements for variety
        time_of_day = "morning" if datetime.now().hour < 12 else "afternoon" if datetime.now().hour < 17 else "evening"
        contextual_greeting = f"Good {time_of_day}! "
        
        # Random motivational elements
        motivational_phrases = [
            "Every small change counts!",
            "You're making a difference!",
            "Small steps lead to big impacts!",
            "Your choices matter!",
            "Keep up the great work!"
        ]
        selected_motivation = random.choice(motivational_phrases)
        
        # Randomly select coaching style and messages with some weighted randomization
        selected_style = random.choice(coaching_styles)
        
        # Sometimes use multiple variations for more variety
        if random.random() < 0.3:  # 30% chance to combine multiple approaches
            selected_car_alt = random.choice(car_alternatives) + " " + random.choice(car_alternatives[:3])
        else:
            selected_car_alt = random.choice(car_alternatives)
            
        selected_praise = random.choice(praise_messages)
        selected_concern = random.choice(concern_messages)
        selected_encouragement = random.choice(encouragement_messages)
        
        # Dynamic prompt with varied content
        prompt = f"""{contextual_greeting}You are a {selected_style}. {selected_motivation} Analyze this user's transportation habits and give them 5 highly personalized tips.

USER'S TRANSPORT DATA:
- Car: {transport_data.car} km ({car_emission:.1f} kg CO2)
- Bus: {transport_data.bus} km ({bus_emission:.1f} kg CO2) 
- Bike: {transport_data.bike} km ({bike_emission:.1f} kg CO2)
- Cycling: {transport_data.cycle} km (0 kg CO2)
- Walking: {transport_data.walking} km (0 kg CO2)
- Total distance: {total_distance} km
- Total CO2: {transport_data.totalEmission:.1f} kg
- Zero-emission percentage: {zero_emission_percentage:.1f}%

ANALYSIS GUIDELINES:
- If car usage is high (>50km): {selected_car_alt}
- If zero-emission percentage is high (>60%): {selected_praise}
- If total emission is high (>10kg): {selected_concern}
- If they walk/cycle a lot: {selected_encouragement}
- Always use their actual numbers and be specific about their habits
- Vary your language and suggestions - don't be repetitive
- Consider their specific distances and suggest realistic alternatives
- Seasonal context: {seasonal_context}
- Time context: {time_of_day}

TONE: Be encouraging, specific, and creative. Make each tip feel unique and personally relevant. Consider the current season and time when making suggestions.

Format each tip as a single line starting with ✅. Return only the 5 tips, one per line."""
        
        # Add more randomization to make responses even more varied
        temperature = random.uniform(0.7, 0.9)  # Vary creativity level
        
        data = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
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

# Database helper functions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_or_create_user(db, email: str, name: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, name=name)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def get_user_challenges(db, user_id: int):
    """Get user challenges and convert to dictionaries for template rendering"""
    user_challenges = db.query(UserChallenge).filter(UserChallenge.user_id == user_id).all()
    
    # Convert to dictionaries with challenge details
    result = []
    for uc in user_challenges:
        challenge = db.query(Challenge).filter(Challenge.id == uc.challenge_id).first()
        if challenge:
            result.append({
                "id": uc.id,
                "user_id": uc.user_id,
                "challenge_id": uc.challenge_id,
                "current_progress": uc.current_progress,
                "is_completed": uc.is_completed,
                "completed_at": uc.completed_at.isoformat() if uc.completed_at else None,
                "joined_at": uc.joined_at.isoformat() if uc.joined_at else None,
                "challenge": {
                    "id": challenge.id,
                    "title": challenge.title,
                    "description": challenge.description,
                    "challenge_type": challenge.challenge_type,
                    "target_value": challenge.target_value,
                    "target_unit": challenge.target_unit,
                    "points_reward": challenge.points_reward,
                    "badge_icon": challenge.badge_icon
                }
            })
    return result

def get_active_challenges(db):
    """Get active challenges and convert to dictionaries for template rendering"""
    challenges = db.query(Challenge).filter(Challenge.is_active == True).all()
    
    # Convert to dictionaries
    result = []
    for challenge in challenges:
        result.append({
            "id": challenge.id,
            "title": challenge.title,
            "description": challenge.description,
            "challenge_type": challenge.challenge_type,
            "target_value": challenge.target_value,
            "target_unit": challenge.target_unit,
            "start_date": challenge.start_date.isoformat() if challenge.start_date else None,
            "end_date": challenge.end_date.isoformat() if challenge.end_date else None,
            "is_active": challenge.is_active,
            "points_reward": challenge.points_reward,
            "badge_icon": challenge.badge_icon,
            "created_at": challenge.created_at.isoformat() if challenge.created_at else None
        })
    return result

def get_user_achievements(db, user_id: int):
    """Get user achievements and convert to dictionaries for template rendering"""
    achievements = db.query(UserAchievement).filter(UserAchievement.user_id == user_id).all()
    
    # Convert to dictionaries
    result = []
    for achievement in achievements:
        result.append({
            "id": achievement.id,
            "user_id": achievement.user_id,
            "achievement_type": achievement.achievement_type,
            "title": achievement.title,
            "description": achievement.description,
            "icon": achievement.icon,
            "earned_at": achievement.earned_at.isoformat() if achievement.earned_at else None
        })
    return result

def create_sample_challenges(db):
    """Create sample challenges if none exist"""
    existing_challenges = db.query(Challenge).count()
    if existing_challenges == 0:
        sample_challenges = [
            Challenge(
                title="Email Reduction Champion",
                description="Reduce your daily email count by 20% for a week",
                challenge_type="individual",
                target_value=20.0,
                target_unit="%",
                points_reward=150,
                badge_icon="📧"
            ),
            Challenge(
                title="Green Commuter",
                description="Use public transport or bike for 5 days straight",
                challenge_type="individual",
                target_value=5.0,
                target_unit="days",
                points_reward=200,
                badge_icon="🚲"
            ),
            Challenge(
                title="Department Sustainability Race",
                description="Compete with other departments to reduce overall emissions",
                challenge_type="team",
                target_value=15.0,
                target_unit="%",
                points_reward=500,
                badge_icon="🏢"
            ),
            Challenge(
                title="Company Carbon Neutral Week",
                description="Achieve company-wide carbon neutrality for one week",
                challenge_type="company",
                target_value=0.0,
                target_unit="kg CO2",
                points_reward=1000,
                badge_icon="🌍"
            ),
            Challenge(
                title="Digital Cleanup Master",
                description="Delete 100 unnecessary emails and files",
                challenge_type="individual",
                target_value=100.0,
                target_unit="items",
                points_reward=120,
                badge_icon="🧹"
            ),
            Challenge(
                title="Sustainable Streak",
                description="Maintain zero-emission travel for 7 consecutive days",
                challenge_type="individual",
                target_value=7.0,
                target_unit="days",
                points_reward=300,
                badge_icon="🔥"
            )
        ]
        
        for challenge in sample_challenges:
            db.add(challenge)
        db.commit()

@app.get("/challenges")
def challenges(request: Request):
    # Check if user is logged in via cookie
    access_token = request.cookies.get("access_token")
    
    if access_token:
        # User is logged in, get data from token
        user_data = get_user_data_from_token(access_token)
        if user_data:
            # Get database session
            db = SessionLocal()
            try:
                # Get or create user
                user = get_or_create_user(db, user_data["user_email"], user_data["user_name"])
                
                # Create sample challenges if none exist
                create_sample_challenges(db)
                
                # Get active challenges
                active_challenges = get_active_challenges(db)
                
                # Get user's current challenges
                user_challenges = get_user_challenges(db, user.id)
                
                # Get user achievements
                user_achievements = get_user_achievements(db, user.id)
                
                # Calculate user stats
                total_points = sum(uc["challenge"]["points_reward"] for uc in user_challenges if uc["is_completed"])
                completed_challenges = len([uc for uc in user_challenges if uc["is_completed"]])
                current_streak = 0  # This would be calculated based on daily activity
                
                return templates.TemplateResponse("challenges.html", {
                    "request": request,
                    **user_data,
                    "active_challenges": active_challenges,
                    "user_challenges": user_challenges,
                    "user_achievements": user_achievements,
                    "total_points": total_points,
                    "completed_challenges": completed_challenges,
                    "current_streak": current_streak,
                    "error": None
                })
            finally:
                db.close()
    
    # User not logged in, redirect to home
    return RedirectResponse("/")

@app.post("/challenges/join/{challenge_id}")
def join_challenge(challenge_id: int, request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"success": False, "message": "Not authenticated"}
    
    user_data = get_user_data_from_token(access_token)
    if not user_data:
        return {"success": False, "message": "Invalid token"}
    
    db = SessionLocal()
    try:
        user = get_or_create_user(db, user_data["user_email"], user_data["user_name"])
        
        # Check if user already joined this challenge
        existing = db.query(UserChallenge).filter(
            UserChallenge.user_id == user.id,
            UserChallenge.challenge_id == challenge_id
        ).first()
        
        if existing:
            return {"success": False, "message": "Already joined this challenge"}
        
        # Join the challenge
        user_challenge = UserChallenge(
            user_id=user.id,
            challenge_id=challenge_id
        )
        db.add(user_challenge)
        db.commit()
        
        return {"success": True, "message": "Successfully joined challenge"}
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error: {str(e)}"}
    finally:
        db.close()

@app.post("/challenges/update-progress/{challenge_id}")
async def update_challenge_progress(challenge_id: int, request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"success": False, "message": "Not authenticated"}
    
    user_data = get_user_data_from_token(access_token)
    if not user_data:
        return {"success": False, "message": "Invalid token"}
    
    # Get progress from request body
    try:
        body = await request.body()
        import json
        data = json.loads(body.decode('utf-8'))
        progress = float(data.get("progress", 0))
    except:
        return {"success": False, "message": "Invalid progress data"}
    
    db = SessionLocal()
    try:
        user = get_or_create_user(db, user_data["user_email"], user_data["user_name"])
        
        # Get user's challenge
        user_challenge = db.query(UserChallenge).filter(
            UserChallenge.user_id == user.id,
            UserChallenge.challenge_id == challenge_id
        ).first()
        
        if not user_challenge:
            return {"success": False, "message": "Challenge not found"}
        
        # Update progress
        user_challenge.current_progress = progress
        
        # Check if challenge is completed
        challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if challenge and progress >= challenge.target_value and not user_challenge.is_completed:
            user_challenge.is_completed = True
            user_challenge.completed_at = func.now()
            
            # Create achievement
            achievement = UserAchievement(
                user_id=user.id,
                achievement_type="badge",
                title=f"Completed: {challenge.title}",
                description=f"Successfully completed the {challenge.title} challenge",
                icon=challenge.badge_icon
            )
            db.add(achievement)
        
        db.commit()
        return {"success": True, "message": "Progress updated"}
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error: {str(e)}"}
    finally:
        db.close()

# Admin functionality
ADMIN_EMAILS = ["admin@zeroprint.com"]  # Add admin emails here
ADMIN_PASSWORD = "admin123"  # Change this to a secure password

def is_admin_user(email: str) -> bool:
    """Check if user is an admin"""
    return email in ADMIN_EMAILS

@app.get("/admin")
def admin_login_page(request: Request):
    """Admin login page"""
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin/login")
async def admin_login(request: Request):
    """Admin login endpoint"""
    try:
        body = await request.body()
        data = json.loads(body.decode('utf-8'))
        email = data.get("email", "")
        password = data.get("password", "")
        
        if email in ADMIN_EMAILS and password == ADMIN_PASSWORD:
            # Return success response
            return {"success": True, "message": "Login successful"}
        else:
            return {"success": False, "message": "Invalid credentials"}
    except Exception as e:
        return {"success": False, "message": "Invalid request data"}

@app.get("/admin/dashboard")
def admin_dashboard(request: Request):
    """Admin dashboard - requires admin authentication"""
    admin_token = request.cookies.get("admin_token")
    if not admin_token or admin_token != "admin_authenticated":
        return RedirectResponse("/admin", status_code=302)
    
    db = SessionLocal()
    try:
        # Get statistics
        total_users = db.query(User).count()
        total_challenges = db.query(Challenge).count()
        active_challenges = db.query(Challenge).filter(Challenge.is_active == True).count()
        total_user_challenges = db.query(UserChallenge).count()
        completed_challenges = db.query(UserChallenge).filter(UserChallenge.is_completed == True).count()
        
        # Get recent users
        recent_users = db.query(User).order_by(User.created_at.desc()).limit(10).all()
        recent_users_data = []
        for user in recent_users:
            recent_users_data.append({
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "created_at": user.created_at.isoformat() if user.created_at else None
            })
        
        # Get recent challenges
        recent_challenges = db.query(Challenge).order_by(Challenge.created_at.desc()).limit(10).all()
        recent_challenges_data = []
        for challenge in recent_challenges:
            recent_challenges_data.append({
                "id": challenge.id,
                "title": challenge.title,
                "challenge_type": challenge.challenge_type,
                "is_active": challenge.is_active,
                "points_reward": challenge.points_reward,
                "created_at": challenge.created_at.isoformat() if challenge.created_at else None
            })
        
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "total_users": total_users,
            "total_challenges": total_challenges,
            "active_challenges": active_challenges,
            "total_user_challenges": total_user_challenges,
            "completed_challenges": completed_challenges,
            "recent_users": recent_users_data,
            "recent_challenges": recent_challenges_data
        })
    finally:
        db.close()

@app.post("/admin/logout")
def admin_logout(request: Request):
    """Admin logout endpoint"""
    response = RedirectResponse("/admin", status_code=302)
    response.delete_cookie("admin_token")
    return response

@app.post("/admin/challenges/add")
async def admin_add_challenge(request: Request):
    """Admin endpoint to add new challenges"""
    admin_token = request.cookies.get("admin_token")
    if not admin_token or admin_token != "admin_authenticated":
        return {"success": False, "message": "Not authenticated"}
    
    try:
        body = await request.body()
        data = json.loads(body.decode('utf-8'))
        
        db = SessionLocal()
        try:
            challenge = Challenge(
                title=data.get("title"),
                description=data.get("description"),
                challenge_type=data.get("challenge_type"),
                target_value=float(data.get("target_value", 0)),
                target_unit=data.get("target_unit"),
                points_reward=int(data.get("points_reward", 100)),
                badge_icon=data.get("badge_icon", "🏆")
            )
            db.add(challenge)
            db.commit()
            return {"success": True, "message": "Challenge added successfully"}
        finally:
            db.close()
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

@app.post("/admin/challenges/update/{challenge_id}")
async def admin_update_challenge(challenge_id: int, request: Request):
    """Admin endpoint to update challenges"""
    admin_token = request.cookies.get("admin_token")
    if not admin_token or admin_token != "admin_authenticated":
        return {"success": False, "message": "Not authenticated"}

    try:
        body = await request.body()
        data = json.loads(body.decode('utf-8'))
        
        db = SessionLocal()
        try:
            challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
            if not challenge:
                return {"success": False, "message": "Challenge not found"}
            
            # Update fields
            if "title" in data:
                challenge.title = data["title"]
            if "description" in data:
                challenge.description = data["description"]
            if "challenge_type" in data:
                challenge.challenge_type = data["challenge_type"]
            if "target_value" in data:
                challenge.target_value = float(data["target_value"])
            if "target_unit" in data:
                challenge.target_unit = data["target_unit"]
            if "points_reward" in data:
                challenge.points_reward = int(data["points_reward"])
            if "badge_icon" in data:
                challenge.badge_icon = data["badge_icon"]
            if "is_active" in data:
                challenge.is_active = bool(data["is_active"])
            
            db.commit()
            return {"success": True, "message": "Challenge updated successfully"}
        finally:
            db.close()
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

@app.delete("/admin/challenges/{challenge_id}")
def admin_delete_challenge(challenge_id: int, request: Request):
    """Admin endpoint to delete challenges"""
    admin_token = request.cookies.get("admin_token")
    if not admin_token or admin_token != "admin_authenticated":
        return {"success": False, "message": "Not authenticated"}
    
    db = SessionLocal()
    try:
        challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if not challenge:
            return {"success": False, "message": "Challenge not found"}
        
        # Delete related user challenges first
        db.query(UserChallenge).filter(UserChallenge.challenge_id == challenge_id).delete()
        
        # Delete the challenge
        db.delete(challenge)
        db.commit()
        return {"success": True, "message": "Challenge deleted successfully"}
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error: {str(e)}"}
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)