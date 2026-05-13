import requests
import json
import os
from fastapi import FastAPI
from upstash_redis import Redis
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis Connection
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

@app.api_route("/api/add-token", methods=["GET", "POST"])
def add_token(token: str, userid: str):
    """Naya token pool mein add karne ke liye"""
    token_entry = json.dumps({"t": token, "u": userid})
    # SADD ensures ki agar same token-id pair hai toh duplicate na ho
    redis.sadd("shared_tokens_pool", token_entry)
    return {"status": "success", "message": f"Token for UID {userid} added to pool!"}

@app.get("/api/all-batches")
def get_all_batches():
    """
    SABHI tokens se batches nikal kar EK HI LIST mein dikhayega.
    """
    # 1. Redis se saare unique tokens ki list uthao
    all_tokens = redis.smembers("shared_tokens_pool")
    
    master_batch_list = [] # Isme sabka data combine hoga
    seen_ids = set() # Course duplication rokne ke liye

    # 2. Har token par loop chalao
    for entry in all_tokens:
        token_data = json.loads(entry)
        t = token_data['t']
        u = token_data['u']
        
        h = HEADERS.copy()
        h.update({"Authorization": t, "User-Id": u})
        
        try:
            # Har token ke liye ClassX se purchases fetch karo
            resp = requests.get(f"{BASE_URL}/get/get_all_purchases", headers=h, params={"userid": u}, timeout=7)
            res_json = resp.json()
            
            if res_json.get("status") == 200:
                current_user_batches = res_json.get("data", [])
                
                for b in current_user_batches:
                    batch_id = str(b.get("id"))
                    
                    # 3. Agar ye batch pehle kisi token mein nahi aaya, toh add karo
                    if batch_id not in seen_ids:
                        clean_batch = {
                            "id": batch_id,
                            "title": b.get("course_name") or b.get("title"),
                            "logo": b.get("course_thumbnail") or b.get("image")
                        }
                        master_batch_list.append(clean_batch)
                        seen_ids.add(batch_id)
        except Exception as e:
            print(f"Error fetching for token {u}: {e}")
            continue

    # 4. Final Result: Isme saare tokens ka mix data hoga
    return {
        "status": 200,
        "total_tokens_scanned": len(all_tokens),
        "total_unique_batches": len(master_batch_list),
        "data": master_batch_list
    }

@app.get("/")
def health():
    return {"status": "Combined Proxy Active"}
