import requests
import json
import os
import asyncio
import httpx  # Parallel requests ke liye isse use karenge
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

# Upstash Credentials
REDIS_URL = "https://allowing-kite-91500.upstash.io"
REDIS_TOKEN = "gQAAAAAAAWVsAAIgcDJmNmE5NTg1NWM5NzM0M2NkYTg5NjkxZWViYjhjOGU5Ng"
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
    token_entry = json.dumps({"t": token, "u": userid})
    redis.sadd("shared_tokens_pool", token_entry)
    return {"status": "success", "message": f"Token saved for UID {userid}"}

async def fetch_user_batches(client, t, u):
    """Single user ke batches fetch karne ka async function"""
    h = HEADERS.copy()
    h.update({"Authorization": t, "User-Id": u})
    try:
        # Timeout ko thoda badha diya hai
        resp = await client.get(f"{BASE_URL}/get/get_all_purchases", headers=h, params={"userid": u}, timeout=15.0)
        if resp.status_code == 200:
            return resp.json().get("data", [])
    except Exception:
        return []
    return []

@app.get("/api/all-batches")
async def get_all_batches():
    # 1. Redis se saare tokens nikalo
    all_tokens_raw = redis.smembers("shared_tokens_pool")
    
    tasks = []
    master_batch_list = []
    seen_ids = set()

    # 2. HTTPX client ka use karke parallel requests bhejna
    async with httpx.AsyncClient() as client:
        for entry in all_tokens_raw:
            data = json.loads(entry)
            tasks.append(fetch_user_batches(client, data['t'], data['u']))
        
        # Saari requests ek saath chalengi
        results = await asyncio.gather(*tasks)

    # 3. Saare results ko merge karna
    for batch_group in results:
        if batch_group:
            for b in batch_group:
                # Agar aapko duplicates bhi chahiye toh ye 'if' hata sakte ho
                # Lekin "itemid" ya "purchaseid" unique hota hai
                bid = str(b.get("purchaseid") or b.get("id") or b.get("itemid"))
                if bid not in seen_ids:
                    master_batch_list.append(b)
                    seen_ids.add(bid)

    return {
        "status": 200,
        "total_tokens_scanned": len(all_tokens_raw),
        "total_batches_returned": len(master_batch_list),
        "data": master_batch_list
    }

@app.get("/")
def home():
    return {"status": "Parallel Proxy Active"}
