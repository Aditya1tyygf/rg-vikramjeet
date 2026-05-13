import json
import asyncio
import httpx
from fastapi import FastAPI, HTTPException
from upstash_redis import Redis
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration ---
REDIS_URL = "https://allowing-kite-91500.upstash.io"
REDIS_TOKEN = "gQAAAAAAAWVsAAIgcDJmNmE5NTg1NWM5NzM0M2NkYTg5NjkxZWViYjhjOGU5Ng"
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

BASE_URL = "https://rgvikramjeetapi.classx.co.in"
HEADERS_TEMPLATE = {
    "Auth-Key": "appxapi",
    "Client-Service": "Appx",
    "Source": "website",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Origin": "https://rankersgurukul.com",
    "Referer": "https://rankersgurukul.com/"
}

# --- Core Token Discovery Logic ---
async def fetch_from_pool(endpoint: str, params: dict):
    """
    Redis pool se tokens uthakar parallelly check karta hai 
    ki kaunsa token data return kar raha hai.
    """
    all_tokens_raw = redis.smembers("shared_tokens_pool")
    if not all_tokens_raw:
        return {"status": 404, "message": "No tokens in pool"}

    async with httpx.AsyncClient() as client:
        # Saare tokens ke liye tasks create karo
        tasks = []
        token_map = [] # Track karne ke liye kaunsa task kis token ka hai

        for entry in all_tokens_raw:
            try:
                data = json.loads(entry)
                t, u = data['t'], data['u']
                h = HEADERS_TEMPLATE.copy()
                h.update({"Authorization": t})
                
                # Kuch endpoints ko userid params mein chahiye hota hai
                current_params = params.copy()
                if "userid" in endpoint: # Auto-inject userid if needed
                    current_params["userid"] = u
                
                tasks.append(client.get(f"{BASE_URL}{endpoint}", headers=h, params=current_params, timeout=10.0))
                token_map.append(u)
            except:
                continue

        # Parallel Execution
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Pehla valid response dhundo jisme data ho
        for i, resp in enumerate(results):
            if isinstance(resp, httpx.Response) and resp.status_code == 200:
                res_data = resp.json()
                # Status check: classx aksar status 200 par bhi empty data bhejta hai
                if res_data.get("status") == "success" or res_data.get("data"):
                    return {
                        "status": 200,
                        "provider_uid": token_map[i],
                        "response": res_data
                    }

    raise HTTPException(status_code=403, detail="Resource not accessible with current token pool")

# --- Endpoints ---

@app.api_route("/api/add-token", methods=["GET", "POST"])
def add_token(token: str, userid: str):
    token_entry = json.dumps({"t": token, "u": userid})
    redis.sadd("shared_tokens_pool", token_entry)
    return {"status": "success", "message": f"Token added for {userid}"}

@app.get("/api/all-batches")
async def get_all_batches():
    """Sare users ke batches ko merge karke dikhata hai"""
    all_tokens_raw = redis.smembers("shared_tokens_pool")
    master_batch_list = []
    seen_ids = set()

    async with httpx.AsyncClient() as client:
        tasks = []
        for entry in all_tokens_raw:
            data = json.loads(entry)
            h = HEADERS_TEMPLATE.copy()
            h.update({"Authorization": data['t']})
            tasks.append(client.get(f"{BASE_URL}/get/get_all_purchases", headers=h, params={"userid": data['u']}))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for resp in results:
        if isinstance(resp, httpx.Response) and resp.status_code == 200:
            batch_data = resp.json().get("data", [])
            for b in batch_data:
                bid = str(b.get("purchaseid") or b.get("id") or b.get("itemid"))
                if bid not in seen_ids:
                    master_batch_list.append(b)
                    seen_ids.add(bid)

    return {"status": 200, "total": len(master_batch_list), "data": master_batch_list}

@app.get("/api/course/subjects")
async def get_subjects(courseid: str):
    return await fetch_from_pool("/get/allsubjectfrmlivecourseclass", {"courseid": courseid, "start": "-1"})

@app.get("/api/course/topics")
async def get_topics(courseid: str, subjectid: str):
    return await fetch_from_pool("/get/alltopicfrmlivecourseclass", {"courseid": courseid, "subjectid": subjectid, "start": "-1"})

@app.get("/api/course/videos")
async def get_videos(courseid: str, subjectid: str, topicid: str, conceptid: str):
    params = {"courseid": courseid, "subjectid": subjectid, "topicid": topicid, "conceptid": conceptid, "start": "0"}
    return await fetch_from_pool("/get/livecourseclassbycoursesubtopconceptapiv3", params)

@app.get("/api/course/video-details")
async def get_video_details(course_id: str, video_id: str):
    params = {"course_id": course_id, "video_id": video_id, "ytflag": "0", "folder_wise_course": "0"}
    return await fetch_from_pool("/get/fetchVideoDetailsById", params)

@app.get("/")
def home():
    return {"status": "Smart Proxy Active", "pool_size": redis.scard("shared_tokens_pool")}
