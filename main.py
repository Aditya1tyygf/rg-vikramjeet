import json
import asyncio
import httpx
from fastapi import FastAPI, HTTPException, Query, APIRouter
from upstash_redis import Redis
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
router = APIRouter()

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

# --- Smart Validator: Checks if token actually has access to the video ---
async def fetch_smart_data(endpoint: str, params: dict, is_video: bool = False):
    all_tokens_raw = redis.smembers("shared_tokens_pool")
    if not all_tokens_raw:
        raise HTTPException(status_code=404, detail="No tokens in pool")

    async with httpx.AsyncClient() as client:
        tasks = []
        uids = []
        
        for entry in all_tokens_raw:
            try:
                data = json.loads(entry)
                h = HEADERS_TEMPLATE.copy()
                h.update({"Authorization": data['t']})
                tasks.append(client.get(f"{BASE_URL}{endpoint}", headers=h, params=params, timeout=15.0))
                uids.append(data['u'])
            except: continue

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, resp in enumerate(results):
            if isinstance(resp, httpx.Response) and resp.status_code == 200:
                res_data = resp.json()
                data_body = res_data.get("data")
                
                # Agar video details mangi hain, toh check karo token khali toh nahi
                if is_video:
                    v_token = data_body.get("video_player_token", "") if data_body else ""
                    if not v_token or len(v_token) < 10:
                        continue # Token invalid hai, skip to next
                
                # Agar data mil gaya (Subject/Topic/Valid Video)
                if res_data.get("status") == "success" or data_body:
                    return {
                        "status": 200,
                        "provider_uid": uids[i],
                        "data": data_body or res_data
                    }
    
    raise HTTPException(status_code=403, detail="Access Denied: No valid purchase token found in pool")

# --- Final Endpoints ---

@router.get("/")
def health():
    return {"status": "Proxy Active", "pool": redis.scard("shared_tokens_pool")}

@router.get("/get-subjects")
async def get_subjects(courseid: str):
    return await fetch_smart_data("/get/allsubjectfrmlivecourseclass", {"courseid": courseid, "start": "-1"})

@router.get("/get-topics")
async def get_topics(courseid: str, subjectid: str):
    return await fetch_smart_data("/get/alltopicfrmlivecourseclass", {"courseid": courseid, "subjectid": subjectid, "start": "-1"})

@router.get("/get-videos")
async def get_videos(courseid: str, subjectid: str, topicid: str):
    p = {"courseid": courseid, "subjectid": subjectid, "topicid": topicid, "conceptid": "1", "start": "0"}
    return await fetch_smart_data("/get/livecourseclassbycoursesubtopconceptapiv3", p)

@router.get("/get-video-details")
async def get_video_details(course_id: str, video_id: str):
    """Specially validated to ensure video_player_token is not empty"""
    p = {"course_id": course_id, "video_id": video_id, "ytflag": "0", "folder_wise_course": "0"}
    return await fetch_smart_data("/get/fetchVideoDetailsById", p, is_video=True)

@router.api_route("/add-token", methods=["GET", "POST"])
def add_token(token: str, userid: str):
    redis.sadd("shared_tokens_pool", json.dumps({"t": token, "u": userid}))
    return {"status": "success"}

# Prefixing all routes with /api for Vercel consistency
app.include_router(router, prefix="/api")
