import json
import asyncio
import httpx
from fastapi import FastAPI, HTTPException, Query
from upstash_redis import Redis
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS settings taki frontend se access block na ho
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

# --- Shared Logic: Token Pool Scanner ---
async def fetch_from_pool(endpoint: str, params: dict):
    # Redis se saare tokens uthao
    all_tokens_raw = redis.smembers("shared_tokens_pool")
    if not all_tokens_raw:
        raise HTTPException(status_code=404, detail="Redis pool is empty. Add tokens first.")

    async with httpx.AsyncClient() as client:
        tasks = []
        uids = []
        
        for entry in all_tokens_raw:
            try:
                token_data = json.loads(entry)
                t = token_data.get('t')
                u = token_data.get('u')
                
                h = HEADERS_TEMPLATE.copy()
                h.update({"Authorization": t})
                
                # Request prepare karo
                tasks.append(client.get(f"{BASE_URL}{endpoint}", headers=h, params=params, timeout=10.0))
                uids.append(u)
            except:
                continue

        # Saari requests ek saath parallel chalao
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check karo kaunsa token kaam kar gaya
        for i, resp in enumerate(results):
            if isinstance(resp, httpx.Response) and resp.status_code == 200:
                res_json = resp.json()
                # Agar ClassX ne valid data diya hai
                if res_json.get("status") == "success" or res_json.get("data"):
                    return {
                        "status": 200,
                        "provider_uid": uids[i],
                        "data": res_json.get("data") or res_json
                    }

    raise HTTPException(status_code=403, detail="Batch not accessible with available tokens.")

# --- Endpoints ---

@app.get("/")
def health_check():
    return {"status": "Proxy Running", "tokens_in_pool": redis.scard("shared_tokens_pool")}

@app.get("/api/get-subjects")
async def get_subjects(courseid: str = Query(...)):
    """Automatic token pick karke subjects dikhayega"""
    return await fetch_from_pool("/get/allsubjectfrmlivecourseclass", {"courseid": courseid, "start": "-1"})

@app.get("/api/get-topics")
async def get_topics(courseid: str = Query(...), subjectid: str = Query(...)):
    """Automatic token pick karke topics dikhayega"""
    return await fetch_from_pool("/get/alltopicfrmlivecourseclass", {"courseid": courseid, "subjectid": subjectid, "start": "-1"})

@app.get("/api/get-videos")
async def get_videos(courseid: str, subjectid: str, topicid: str):
    """Automatic token pick karke videos dikhayega"""
    params = {"courseid": courseid, "subjectid": subjectid, "topicid": topicid, "conceptid": "1", "start": "0"}
    return await fetch_from_pool("/get/livecourseclassbycoursesubtopconceptapiv3", params)

@app.get("/api/get-video-details")
async def get_video_details(course_id: str, video_id: str):
    """Automatic token pick karke stream URL nikalega"""
    params = {"course_id": course_id, "video_id": video_id, "ytflag": "0", "folder_wise_course": "0"}
    return await fetch_from_pool("/get/fetchVideoDetailsById", params)

@app.api_route("/api/add-token", methods=["GET", "POST"])
def add_token(token: str, userid: str):
    token_entry = json.dumps({"t": token, "u": userid})
    redis.sadd("shared_tokens_pool", token_entry)
    return {"status": "success", "message": f"Token saved for UID {userid}"}
