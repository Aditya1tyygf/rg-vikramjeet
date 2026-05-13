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

# --- Shared Logic: Smart Token Picker ---
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
                res_json = resp.json()
                data_body = res_json.get("data")
                
                # Check for Video Details: token khali nahi hona chahiye
                if is_video:
                    v_token = data_body.get("video_player_token", "") if data_body else ""
                    if not v_token or len(v_token) < 10:
                        continue 
                
                # Check for other data
                if res_json.get("status") == "success" or data_body:
                    return {
                        "status": 200,
                        "provider_uid": uids[i],
                        "data": data_body or res_json
                    }
    
    raise HTTPException(status_code=403, detail="Batch not purchased or access denied by all tokens")

# --- Endpoints ---

@router.get("/")
def health():
    return {"status": "Proxy Active", "pool_count": redis.scard("shared_tokens_pool")}

# 1. Get All Batches (Merge results from all tokens)
@router.get("/all-batches")
async def get_all_batches():
    all_tokens_raw = redis.smembers("shared_tokens_pool")
    master_list = []
    seen = set()
    async with httpx.AsyncClient() as client:
        tasks = []
        uids = []
        for t_entry in all_tokens_raw:
            data = json.loads(t_entry)
            h = {**HEADERS_TEMPLATE, "Authorization": data['t']}
            tasks.append(client.get(f"{BASE_URL}/get/get_all_purchases", headers=h, params={"userid": data['u']}))
            uids.append(data['u'])
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, r in enumerate(results):
            if isinstance(r, httpx.Response) and r.status_code == 200:
                for b in r.json().get("data", []):
                    bid = str(b.get("purchaseid") or b.get("id"))
                    if bid not in seen:
                        b["owner_uid"] = uids[i]
                        master_list.append(b)
                        seen.add(bid)
    return {"status": 200, "data": master_list}

# 2. Get Subjects
@router.get("/get-subjects")
async def get_subjects(courseid: str):
    return await fetch_smart_data("/get/allsubjectfrmlivecourseclass", {"courseid": courseid, "start": "-1"})

# 3. Get Topics
@router.get("/get-topics")
async def get_topics(courseid: str, subjectid: str):
    return await fetch_smart_data("/get/alltopicfrmlivecourseclass", {"courseid": courseid, "subjectid": subjectid, "start": "-1"})

# 4. Get Videos List
@router.get("/get-videos")
async def get_videos(courseid: str, subjectid: str, topicid: str):
    p = {"courseid": courseid, "subjectid": subjectid, "topicid": topicid, "conceptid": "1", "start": "0"}
    return await fetch_smart_data("/get/livecourseclassbycoursesubtopconceptapiv3", p)

# 5. Get Video Details (Validated Token)
@router.get("/get-video-details")
async def get_video_details(course_id: str, video_id: str):
    p = {"course_id": course_id, "video_id": video_id, "ytflag": "0", "folder_wise_course": "0"}
    return await fetch_smart_data("/get/fetchVideoDetailsById", p, is_video=True)

# 6. Add Token to Redis
@router.api_route("/add-token", methods=["GET", "POST"])
def add_token(token: str, userid: str):
    redis.sadd("shared_tokens_pool", json.dumps({"t": token, "u": userid}))
    return {"status": "success", "message": f"Token saved for {userid}"}

app.include_router(router, prefix="/api")
