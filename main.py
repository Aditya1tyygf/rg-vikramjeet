import requests
import json
import os
from fastapi import FastAPI
from upstash_redis import Redis
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Nayi Upstash Credentials
REDIS_URL = "https://allowing-kite-91500.upstash.io"
REDIS_TOKEN = "gQAAAAAAAWVsAAIgcDJmNmE5NTg1NWM5NzM0M2NkYTg5NjkxZWViYjhjOGU5Ng"

# Redis Connection Initialize
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

BASE_URL = "https://rgvikramjeetapi.classx.co.in"
HEADERS = {
    "Auth-Key": "appxapi",
    "Client-Service": "Appx",
    "Source": "website",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# --- 1. TOKEN ADD KARNE KA ENDPOINT ---
@app.api_route("/api/add-token", methods=["GET", "POST"])
def add_token(token: str, userid: str):
    """
    User ka Token aur ID Redis pool mein save karega.
    """
    token_entry = json.dumps({"t": token, "u": userid})
    # SADD duplicate tokens ko khud hi filter kar deta hai
    redis.sadd("shared_tokens_pool", token_entry)
    return {"status": "success", "message": f"Token saved for UID {userid}"}

# --- 2. SABKE BATCHES MIX KARKE FULL JSON DIKHANE KA ENDPOINT ---
@app.get("/api/all-batches")
def get_all_batches():
    """
    Pool ke saare tokens se data fetch karke ek saath Full JSON dikhayega.
    """
    # Redis se saare saved tokens ki list uthao
    all_tokens = redis.smembers("shared_tokens_pool")
    
    master_batch_list = []
    seen_ids = set()

    for entry in all_tokens:
        try:
            token_data = json.loads(entry)
            t, u = token_data['t'], token_data['u']
            
            h = HEADERS.copy()
            h.update({"Authorization": t, "User-Id": u})
            
            # Live Fetching from Purchases Endpoint
            resp = requests.get(f"{BASE_URL}/get/get_all_purchases", headers=h, params={"userid": u}, timeout=10)
            res_json = resp.json()
            
            if res_json.get("status") == 200:
                current_batches = res_json.get("data", [])
                
                for b in current_batches:
                    # Unique ID check (Duplicate courses handle karne ke liye)
                    batch_id = str(b.get("id") or b.get("course_id"))
                    
                    if batch_id not in seen_ids:
                        # Hum poora 'b' (Full JSON object) list mein daal rahe hain
                        master_batch_list.append(b)
                        seen_ids.add(batch_id)
        except Exception:
            continue

    return {
        "status": 200,
        "total_tokens_in_pool": len(all_tokens),
        "total_unique_batches": len(master_batch_list),
        "data": master_batch_list # Pura Original JSON yahan aayega
    }

@app.get("/")
def home():
    return {"status": "Ready", "db": "Upstash Connected"}
