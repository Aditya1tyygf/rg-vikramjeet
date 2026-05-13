import requests
import json
from fastapi import FastAPI, HTTPException
from upstash_redis import Redis
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Shared Batch Pool API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis Setup
REDIS_URL = os.getenv("REDIS_URL", "https://allowing-kite-91500.upstash.io")
REDIS_TOKEN = os.getenv("REDIS_TOKEN", "gQAAAAAAAWVsAAIgcDJmNmE5NTg1NWM5NzM0M2NkYTg5NjkxZWViYjhjOGU5Ng")
redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)

BASE_URL = "https://rgvikramjeetapi.classx.co.in"
HEADERS = {"Auth-Key": "appxapi", "Client-Service": "Appx", "Source": "website"}

# --- Endpoints ---

@app.post("/api/import-batches")
def import_to_pool(token: str, userid: str):
    """User apna token dalega aur uske batches shared pool mein jud jayenge"""
    h = HEADERS.copy()
    h.update({"Authorization": token, "User-Id": userid})
    try:
        resp = requests.get(f"{BASE_URL}/get/mycourseweb", headers=h, params={"userid": userid})
        data = resp.json()
        if data.get("status") == 200:
            batches = data.get("data", [])
            for b in batches:
                # Batch info + token mapping save ho rahi hai
                b_info = {
                    "id": b.get("id"),
                    "name": b.get("course_name"),
                    "img": b.get("course_thumbnail"),
                    "owner_token": token,
                    "owner_id": userid
                }
                # Redis Set (SADD) duplicate batches ko khud handle kar lega
                redis.sadd("pool:all_batches", json.dumps(b_info))
            return {"status": "success", "msg": f"{len(batches)} batches added to pool"}
        return {"status": "error", "msg": "Invalid Token or ID"}
    except:
        raise HTTPException(status_code=500, detail="Import failed")

@app.get("/api/all-batches")
def get_pool():
    """Shared pool se saare batches dikhayega"""
    raw = redis.smembers("pool:all_batches")
    return [json.loads(b) for b in raw]

@app.get("/api/subjects")
def get_subjects(courseid: str, token: str, userid: str):
    """Specific batch ke subjects"""
    h = HEADERS.copy()
    h.update({"Authorization": token, "User-Id": userid})
    resp = requests.get(f"{BASE_URL}/get/allsubjectfrmlivecourseclass", headers=h, params={"courseid": courseid})
    return resp.json()

@app.get("/api/topics")
def get_topics(courseid: str, subjectid: str, token: str, userid: str):
    """Subject ke topics"""
    h = HEADERS.copy()
    h.update({"Authorization": token, "User-Id": userid})
    params = {"courseid": courseid, "subjectid": subjectid, "start": "-1"}
    resp = requests.get(f"{BASE_URL}/get/alltopicfrmlivecourseclass", headers=h, params=params)
    return resp.json()

@app.get("/api/videos")
def get_videos(courseid: str, subjectid: str, topicid: str, token: str, userid: str):
    """Videos aur PDFs"""
    h = HEADERS.copy()
    h.update({"Authorization": token, "User-Id": userid})
    params = {"courseid": courseid, "subjectid": subjectid, "topicid": topicid, "conceptid": "1", "start": "0"}
    resp = requests.get(f"{BASE_URL}/get/livecourseclassbycoursesubtopconceptapiv3", headers=h, params=params)
    return resp.json()

@app.get("/")
def health():
    return {"status": "Shared Pool API is Live"}
