import os
import sqlite3
import uuid
import json
import math
import traceback
import time
from datetime import datetime
from fastapi import FastAPI, UploadFile, Form, File, HTTPException, BackgroundTasks, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from google.cloud import storage, bigquery, firestore
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET", "hackathon-secret-key-123"))

# Ensure recordings directory exists
if not os.path.exists("recordings"):
    os.makedirs("recordings")

# Mount recordings (keep for local debugging, but cloud will use GCS)
app.mount("/recordings", StaticFiles(directory="recordings"), name="recordings")

# Initialize Cloud Clients (Will use ADC in Cloud Run)
try:
    GCS_CLIENT = storage.Client()
    BQ_CLIENT = bigquery.Client()
    DB_CLIENT = firestore.Client()
    BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "aura-nexus-recordings")
    BQ_DATASET = os.environ.get("BQ_DATASET", "aura_nexus")
except Exception as e:
    print(f"DEBUG: Cloud Client init failed (Local mode suspected): {e}")
    GCS_CLIENT = BQ_CLIENT = DB_CLIENT = None

# Configure Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    print(f"DEBUG: GEMINI_API_KEY detected (Length: {len(GEMINI_API_KEY)})")
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("WARNING: GEMINI_API_KEY NOT FOUND in environment!")

# Auth Dependency
def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=303, detail="Not authenticated", headers={"Location": "/"})
    return user

async def admin_only(request: Request):
    user = get_current_user(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user

def init_db():
    conn = sqlite3.connect('emergencies.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS incidents 
                      (id TEXT PRIMARY KEY, lat REAL, lng REAL, category TEXT, urgency REAL, 
                       summary TEXT, transcript TEXT, sounds TEXT, silent_alert BOOLEAN, 
                       status TEXT, responder_id TEXT, confidence REAL, analysis TEXT,
                       timestamp TEXT, traffic_notes TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS responders 
                      (id TEXT PRIMARY KEY, lat REAL, lng REAL, category TEXT, name TEXT, city TEXT)''')
    
    cursor.execute("SELECT COUNT(*) FROM responders")
    if cursor.fetchone()[0] == 0:
        mock_responders = [
            ("RES-001", 28.6139, 77.2090, "POLICE", "Delhi PCR Unit 12", "Delhi"),
            ("RES-002", 19.0760, 72.8777, "EMS", "Mumbai City Ambulance", "Mumbai"),
            ("RES-003", 12.9716, 77.5946, "FIRE", "Bangalore Fire Brigade", "Bangalore"),
            ("RES-004", 13.0827, 80.2707, "POLICE", "Chennai Patrol 5", "Chennai"),
            ("RES-005", 22.5726, 88.3639, "RESCUE", "Kolkata Disaster Rescue", "Kolkata"),
            ("RES-006", 17.3850, 78.4867, "EMS", "Hyderabad Emergency Services", "Hyderabad"),
            ("RES-007", 28.6692, 77.4538, "FIRE", "NCR Fire Unit 2", "Ghaziabad"),
            ("RES-008", 19.2183, 72.9781, "POLICE", "Thane Main Police", "Thane"),
        ]
        cursor.executemany("INSERT INTO responders (id, lat, lng, category, name, city) VALUES (?, ?, ?, ?, ?, ?)", mock_responders)
    conn.commit()
    conn.close()

init_db()

def get_haversine_dist(lat1, lon1, lat2, lon2):
    R = 6371
    dLat, dLon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

async def analyze_audio_task(incident_id: str, file_bytes: bytes, content_type: str):
    print(f"DEBUG: Starting background analysis for {incident_id} (Size: {len(file_bytes)} bytes)")
    prompt = """
    CRITICAL: YOU ARE THE REASONING ENGINE FOR A LIFE-SAVING EMERGENCY SYSTEM.
    1. EXTRAC EVERYTHING: Transcribe every single humany word spoke in the audio into 'transcript'. If someone is whispering, transcribe it.
    2. ANALYZE SOUNDS: Identify gunshots, sirens, crashes, or breathing patterns in 'sounds'.
    3. REASONING: Explain your logic in 'analysis' (e.g. "Victim is whispering 'help' while sirens are 200m away").
    
    OUTPUT RAW JSON ONLY:
    {
      "category": "POLICE/EMS/FIRE/RESCUE",
      "urgency": 0.0-1.0, 
      "summary": "10-word summary",
      "transcript": "Full text of speech",
      "sounds": ["siren", "scream"],
      "confidence": 0.0-1.0,
      "analysis": "...",
      "silent_alert": bool
    }
    """
    model = genai.GenerativeModel("gemini-2.5-flash") # Deploy Test
    # New Test
    try:
        response = model.generate_content([{"mime_type": content_type, "data": file_bytes}, prompt])
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)
        print(f"DEBUG: Gemini response received for {incident_id}")
    except Exception as e:
        print(f"DEBUG: Gemini analysis failed: {str(e)}")
        data = {"category": "UNKNOWN", "urgency": 1.0, "summary": "Analysis Failure", "transcript": "[Unintelligible]", "sounds": [], "confidence": 0.1, "analysis": f"AI Engine Error: {str(e)}", "silent_alert": False}

    conn = sqlite3.connect('emergencies.db'); cursor = conn.cursor()
    cursor.execute("""UPDATE incidents SET category=?, urgency=?, summary=?, transcript=?, 
                      sounds=?, silent_alert=?, status='DISPATCHED', confidence=?, analysis=? 
                      WHERE id=?""",
                   (data.get("category", "UNKNOWN"), data.get("urgency", 0.5), data.get("summary", ""), 
                    data.get("transcript", ""), json.dumps(data.get("sounds", [])), data.get("silent_alert", False),
                    data.get("confidence", 0.5), data.get("analysis", ""), incident_id))
    conn.commit(); conn.close()

@app.get("/")
def read_root():
    with open("login.html", "r") as f: return HTMLResponse(f.read())

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == "admin" and password == "admin":
        request.session["user"] = {"role": "admin", "name": "Admin"}
        return RedirectResponse("/admin", 303)
    if username == "user" and password == "user":
        request.session["user"] = {"role": "user", "name": "User"}
        return RedirectResponse("/user", 303)
    return HTMLResponse("Invalid credentials.", 401)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", 303)

@app.get("/admin")
def admin_view(request: Request, user: dict = Depends(admin_only)):
    with open("admin.html", "r") as f: return HTMLResponse(f.read())

@app.get("/user")
def user_view(request: Request, user: dict = Depends(get_current_user)):
    with open("user.html", "r") as f: return HTMLResponse(f.read())

@app.get("/responders")
def get_responders():
    conn = sqlite3.connect('emergencies.db'); cursor = conn.cursor()
    cursor.execute("SELECT * FROM responders"); data = [{"id": r[0], "lat": r[1], "lng": r[2], "category": r[3], "name": r[4], "city": r[5]} for r in cursor.fetchall()]
    conn.close(); return data

@app.post("/dispatch")
async def process_dispatch(bg_tasks: BackgroundTasks, audio_file: UploadFile = File(None), text: str = Form(None), lat: float = Form(...), lng: float = Form(...)):
    incident_id = str(uuid.uuid4())
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    file_bytes = None
    if audio_file:
        file_bytes = await audio_file.read()
        # 1. Save locally (fallback)
        filepath = os.path.join("recordings", f"{incident_id}.webm")
        with open(filepath, "wb") as f: f.write(file_bytes)
        
        # 2. Upload to Cloud Storage (Professional Grade)
        if GCS_CLIENT:
            try:
                bucket = GCS_CLIENT.bucket(BUCKET_NAME)
                blob = bucket.blob(f"recordings/{incident_id}.webm")
                blob.upload_from_string(file_bytes, content_type=audio_file.content_type or "audio/webm")
                print(f"DEBUG: Uploaded {incident_id} to GCS bucket {BUCKET_NAME}")
            except Exception as e: print(f"DEBUG: GCS Upload failed: {e}")
    
    # Auto-find nearest responder instantly
    conn = sqlite3.connect('emergencies.db'); cursor = conn.cursor()
    cursor.execute("SELECT * FROM responders")
    all_res = cursor.fetchall()
    nearest = None; min_d = 999999
    for r in all_res:
        d = get_haversine_dist(lat, lng, r[1], r[2])
        if d < min_d: min_d = d; nearest = r
    
    traffic = ["Heavy traffic in city center", "Clear roads", "Minor congestion", "Signal delays"][int(time.time()) % 4]
    
    # Create incident STUB instantly
    status = "ANALYZING" if file_bytes else "DISPATCHED"
    summary = "Acoustic Hub Processing..." if file_bytes else (text[:30] + "..." if text else "Text Emergency")
    transcript = "[Analyzing audio telemetry...]" if file_bytes else (text or "Manual text alert.")
    cat = "PENDING" if file_bytes else "RESCUE"
    
    incident_data = (incident_id, lat, lng, cat, 0.5, summary, 
                    transcript, "[]", False, status, 
                    nearest[0] if nearest else None, 0.0, "Real-time reasoning in progress...", ts, traffic)
    
    cursor.execute("INSERT INTO incidents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", incident_data)
    conn.commit(); conn.close()
    
    # 3. Log to BigQuery (Analytical Audit Trail)
    if BQ_CLIENT:
        try:
            table_id = f"{BQ_CLIENT.project}.{BQ_DATASET}.incidents"
            row = {"id": incident_id, "lat": lat, "lng": lng, "category": cat, "urgency": 0.5, "status": status, "timestamp": ts}
            BQ_CLIENT.insert_rows_json(table_id, [row])
            print(f"DEBUG: Logged incident {incident_id} to BigQuery")
        except Exception as e: print(f"DEBUG: BigQuery log failed: {e}")

    # 4. Update Firestore (Real-time Live Feed)
    if DB_CLIENT:
        try:
            doc_ref = DB_CLIENT.collection("incidents").document(incident_id)
            doc_ref.set({"lat": lat, "lng": lng, "category": cat, "status": status, "timestamp": ts, 
                         "responder_id": nearest[0] if nearest else None})
            print(f"DEBUG: Published incident {incident_id} to Firestore")
        except Exception as e: print(f"DEBUG: Firestore update failed: {e}")

    if file_bytes:
        # Queue Gemini analysis in background
        bg_tasks.add_task(analyze_audio_task, incident_id, file_bytes, audio_file.content_type or "audio/webm")
    
    return {"incident_id": incident_id, "status": status, "responder_id": nearest[0] if nearest else None}

@app.post("/override_dispatch")
def override_dispatch(incident_id: str = Form(...), status: str = Form(...)):
    conn = sqlite3.connect('emergencies.db'); cursor = conn.cursor()
    cursor.execute("UPDATE incidents SET status=? WHERE id=?", (status, incident_id))
    conn.commit(); conn.close()
    return {"status": "success"}

@app.get("/incidents")
def get_incidents():
    conn = sqlite3.connect('emergencies.db'); cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents"); rows = cursor.fetchall(); conn.close()
    return [{"id": r[0], "lat": r[1], "lng": r[2], "category": r[3], "urgency": r[4], "summary": r[5], "transcript": r[6], "sounds": json.loads(r[7]), "silent_alert": r[8], "status": r[9], "responder_id": r[10], "confidence": r[11], "analysis": r[12], "timestamp": r[13], "traffic": r[14]} for r in rows]
