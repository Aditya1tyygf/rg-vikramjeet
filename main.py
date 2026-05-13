import requests
import json
import os
from fastapi import FastAPI, HTTPException
from upstash_redis import Redis
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Community Shared Batch API")

# CORS Setup: Taaki tumhara Web App is API ko call kar sake
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis Configuration (Vercel ke Environment Variables mein daal dena)
REDIS_URL = os.getenv("REDIS_URL", "https://allowing-kite-91500.upstash.io")
REDIS_TOKEN = os.getenv("REDIS_TOKEN", "gQAAAAAAAWVsAAIgcDJmNmE5NTg1NWM5NzM0M2NkYTg5NjkxZWViYjhjOGU5Ng")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

BASE_URL = "https://rgvikramjeetapi.classx.co.in"
HEADERS = {
    "Auth-Key": "appxapi",
    "Client-Service": "Appx",
    "Source": "website",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# --- ENDPOINT 1: TOKEN SAVE KARNA ---
@app.api_route("/api/add-token", methods=["GET", "POST"])
def add_token(token: str, userid: str):
    """
    Jab bhi koi user apna token/id dalega, woh Redis mein ek 'Set' mein save ho jayega.
    Set use karne se duplicate tokens apne aap remove ho jate hain.
    """
    token_entry = json.dumps({"t": token, "u": userid})
    redis.sadd("shared_tokens_pool", token_entry)
    return {"status": "success", "message": "Token added to community pool"}

# --- ENDPOINT 2: SABKE BATCHES EK SAATH DIKHANA ---
@app.get("/api/all-batches")
def get_all_shared_batches():
    """
    Ye Redis se saare tokens nikalega aur sabke batches ko ek badi list mein merge kar dega.
    """
    all_token_data = redis.smembers("shared_tokens_pool")
    combined_batches = []
    seen_ids = set() # Duplicate batches (jo multiple logo ke paas hain) unhe ek hi baar dikhane ke liye

    for entry in all_token_data:
        data = json.loads(entry)
        t, u = data['t'], data['u']
        
        h = HEADERS.copy()
        h.update({"Authorization": t, "User-Id": u})
        
        try:
            # Live Fetch from ClassX
            resp = requests.get(f"{BASE_URL}/get/get_all_purchases", headers=h, params={"userid": u}, timeout=7)
            res_json = resp.json()
            
            if res_json.get("status") == 200:
                user_batches = res_json.get("data", [])
                for b in user_batches:
                    batch_id = b.get("id")
                    if batch_id not in seen_ids:
                        # Batch ke saath uska 'Access Token' chipka dete hain taaki click karne pe chale
                        b["owner_token"] = t
                        b["owner_userid"] = u
                        combined_batches.append(b)
                        seen_ids.add(batch_id)
        except:
            continue # Expired token ya server error pe skip karo

    return {"total": len(combined_batches), "batches": combined_batches}

# --- ENDPOINT 3: VIDEOS/SUBJECTS FETCH KARNA ---
@app.get("/api/get-content")
def get_content(endpoint: str, courseid: str, token: str, userid: str, subjectid: str = None, topicid: str = None):
    """
    Generic endpoint jo subjects, topics aur videos fetch karega 
    unhi tokens ka use karke jo batch ke saath save huye the.
    """
    h = HEADERS.copy()
    h.update({"Authorization": token, "User-Id": userid})
    params = {"courseid": courseid, "userid": userid}
    
    if subjectid: params["subjectid"] = subjectid
    if topicid: params["topicid"] = topicid
    
    target_url = f"{BASE_URL}/get/{endpoint}"
    resp = requests.get(target_url, headers=h, params=params)
    return resp.json()

@app.get("/")
def health():
    return {"status": "Community API is running"}
