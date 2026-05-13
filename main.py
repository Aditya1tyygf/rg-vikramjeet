import requests
import json
import os
from fastapi import FastAPI, HTTPException
from upstash_redis import Redis
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Shared Batch Pool API")

# CORS Middleware: Taaki Web App se API call block na ho
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration: Upstash Redis (Vercel Variables se connect hoga)
REDIS_URL = os.getenv("REDIS_URL", "https://winning-lioness-97755.upstash.io")
REDIS_TOKEN = os.getenv("REDIS_TOKEN", "gQAAAAAAAX3bAAIgcDExMDY4NGY2OWZlZGY0OWY0ODA0NmNmZDNlM2JhNGUxOA")

redis = Redis(url=REDIS_URL, token=REDIS_TOKEN)
BASE_URL = "https://rgvikramjeetapi.classx.co.in"
HEADERS = {"Auth-Key": "appxapi", "Client-Service": "Appx", "Source": "website"}

# ================== ENDPOINTS ==================

@app.api_route("/api/import-batches", methods=["GET", "POST"])
def import_batches(token: str, userid: str):
    """
    Dono tariko ko support karta hai:
    1. Web App: POST request ke through.
    2. Direct API: Browser mein URL hit karke (GET).
    """
    h = HEADERS.copy()
    h.update({"Authorization": token, "User-Id": userid})
    
    try:
        resp = requests.get(f"{BASE_URL}/get/mycourseweb", headers=h, params={"userid": userid}, timeout=10)
        data = resp.json()
        
        if data.get("status") == 200:
            batches = data.get("data", [])
            for b in batches:
                b_info = {
                    "id": b.get("id"),
                    "name": b.get("course_name"),
                    "img": b.get("course_thumbnail"),
                    "owner_token": token,
                    "owner_id": userid
                }
                # Redis Set mein add karo (SADD ensures no duplicates)
                redis.sadd("pool:all_batches", json.dumps(b_info))
            
            return {"status": "success", "msg": f"{len(batches)} batches added to shared pool"}
        return {"status": "error", "msg": "Invalid Token ya User-ID"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}

@app.get("/api/all-batches")
def get_shared_pool():
    """Shared pool se saare logo ke batches fetch karne ke liye"""
    try:
        raw_data = redis.smembers("pool:all_batches")
        all_batches = [json.loads(b) for b in raw_data]
        return {"total": len(all_batches), "batches": all_batches}
    except:
        return {"total": 0, "batches": []}

@app.get("/api/subjects")
def get_subjects(courseid: str, token: str, userid: str):
    h = HEADERS.copy()
    h.update({"Authorization": token, "User-Id": userid})
    resp = requests.get(f"{BASE_URL}/get/allsubjectfrmlivecourseclass", headers=h, params={"courseid": courseid})
    return resp.json()

@app.get("/api/topics")
def get_topics(courseid: str, subjectid: str, token: str, userid: str):
    h = HEADERS.copy()
    h.update({"Authorization": token, "User-Id": userid})
    params = {"courseid": courseid, "subjectid": subjectid, "start": "-1"}
    resp = requests.get(f"{BASE_URL}/get/alltopicfrmlivecourseclass", headers=h, params=params)
    return resp.json()

@app.get("/api/videos")
def get_videos(courseid: str, subjectid: str, topicid: str, token: str, userid: str):
    h = HEADERS.copy()
    h.update({"Authorization": token, "User-Id": userid})
    params = {"courseid": courseid, "subjectid": subjectid, "topicid": topicid, "conceptid": "1", "start": "0"}
    resp = requests.get(f"{BASE_URL}/get/livecourseclassbycoursesubtopconceptapiv3", headers=h, params=params)
    return resp.json()

@app.get("/")
def home():
    return {"status": "Online", "mode": "Shared Pool Proxy"}
