import json
import asyncio
import httpx
from fastapi import FastAPI, HTTPException, Query, APIRouter
from upstash_redis import Redis
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
router = APIRouter()

# CORS settings taaki frontend se error na aaye
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

# --- Internal Helper for Video/Data Validation ---
async def fetch_smart_data(endpoint: str, params: dict, is_video: bool = False):
    all_tokens_raw = redis.smembers("shared_tokens_pool")
    if not all_tokens_raw:
        raise HTTPException(status_code=404, detail="No tokens in pool")

    async with httpx.AsyncClient() as client:
        tasks = []
        for entry in all_tokens_raw:
            try:
                data = json.loads(entry)
                h = {**HEADERS_TEMPLATE, "Authorization": data['t']}
                tasks.append(client.get(f"{BASE_URL}{endpoint}", headers=h, params=params, timeout=12.0))
            except: continue

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for resp in results:
            if isinstance(resp, httpx.Response) and resp.status_code == 200:
                res_json = resp.json()
                data_body = res_json.get("data")
                
                if is_video:
                    v_token = data_body.get("video_player_token", "") if data_body else ""
                    if not v_token or len(v_token) < 10:
                        continue 
                
                if res_json.get("status") == "success" or data_body:
                    return {"status": 200, "data": data_body or res_json}
    
    raise HTTPException(status_code=403, detail="Access denied by all available tokens")

# --- Endpoints ---

@router.get("/")
def api_status():
    """Check how many tokens are active in your pool"""
    token_count = redis.scard("shared_tokens_pool")
    return {
        "status": "RG-MAXX Proxy Online", 
        "total_tokens_in_pool": token_count,
        "message": "Use /api/all-batches to see courses"
    }

@router.get("/clear-pool-secret-789")
def clear_pool():
    """Reset everything if batches are stuck"""
    redis.delete("shared_tokens_pool")
    return {"status": "success", "message": "Redis pool cleared. Now add fresh tokens."}

@router.get("/all-batches")
async def get_all_batches():
    """Fetch ONLY Courses, No Test Series, No Owner UID"""
    all_tokens_raw = redis.smembers("shared_tokens_pool")
    if not all_tokens_raw:
        return {"status": 200, "total": 0, "data": []}

    master_list = []
    seen_ids = set()

    async with httpx.AsyncClient() as client:
        tasks = []
        for t_entry in all_tokens_raw:
            try:
                data = json.loads(t_entry)
                h = {**HEADERS_TEMPLATE, "Authorization": data['t']}
                tasks.append(client.get(f"{BASE_URL}/get/get_all_purchases", headers=h, params={"userid": data['u']}, timeout=10.0))
            except: continue
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, httpx.Response) and r.status_code == 200:
                for item in r.json().get("data", []):
                    # Filter: Sirf 'Course' hona chahiye
                    if item.get("itemtype") == "Course" and item.get("coursedt"):
                        inner = item["coursedt"][0]
                        batch_id = str(inner.get("id"))
                        if batch_id not in seen_ids:
                            master_list.append({
                                "id": batch_id,
                                "name": inner.get("course_name"),
                                "thumbnail": inner.get("course_thumbnail"),
                                "type": "Course",
                                "expiry": item.get("enddatetime")
                            })
                            seen_ids.add(batch_id)
    return {"status": 200, "total": len(master_list), "data": master_list}

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
    p = {"course_id": course_id, "video_id": video_id, "ytflag": "0", "folder_wise_course": "0"}
    return await fetch_smart_data("/get/fetchVideoDetailsById", p, is_video=True)

@router.api_route("/add-token", methods=["GET", "POST"])
def add_token(token: str, userid: str):
    redis.sadd("shared_tokens_pool", json.dumps({"t": token, "u": userid}))
    return {"status": "success"}

app.include_router(router, prefix="/api")
