# 🚨 Aura Nexus - Universal Emergency Bridge

Aura Nexus is a professional-grade, multi-service emergency communication platform designed to bridge the gap between victims and first responders using advanced AI and real-time telemetry.

## ✨ Key Features
- **Acoustic Intelligence Hub**: Uses Gemini 2.5 AI to transcribe audio telemetry, analyze background sounds (sirens, crashes, breathing patterns), and generate reasoning summaries.
- **Hybrid Reporting**: Fallback to secure text reporting if a user is unable to speak or requires a silent alert.
- **Crisis Center Dashboard**: A fully-featured admin interface for dispatchers with live mapping, real-time incident updates, and audio playback.
- **Live Responder Tracking**: Victims can track the exact location of the approaching first responder on a dynamic map with ETA updates.
- **Google Cloud Powered**:
  - **Cloud Storage (GCS)**: Persistent, secure storage for all audio recordings.
  - **BigQuery**: Enterprise-grade analytical logging and audit trails for all emergency incidents.
  - **Firestore**: Real-time state publishing for low-latency incident and responder tracking.
- **Premium Aesthetics**: High-end glassmorphism UI, pulsing data markers, and `aria-label` compliant accessibility features.

## 🛠️ Tech Stack
- **Backend**: FastAPI, SQLite (Local Data), Google Cloud SDK (Storage, BigQuery, Firestore)
- **Frontend**: HTML5, Vanilla CSS, JS, Leaflet.js (Maps)
- **AI Integration**: Google Generative AI (Gemini 2.5 Flash)
- **Security**: Starlette SessionMiddleware

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- A Google Cloud Project with the required APIs enabled (Storage, BigQuery, Firestore)
- A Gemini API Key
- Google Application Default Credentials (ADC) configured locally, or run inside Cloud Run.

### 1. Configure Environment
Create a `.env` file in the root directory and add your secret keys:
```env
GEMINI_API_KEY=your_gemini_api_key
GCS_BUCKET_NAME=your_gcs_bucket_name
BQ_DATASET=your_bigquery_dataset
SESSION_SECRET=your_secure_session_secret
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Server
```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```
Navigate to:
- **Application Flow**: `http://localhost:8080/`
- **Victim Portal**: `http://localhost:8080/user`
- **Crisis Center**: `http://localhost:8080/admin`

*(Default Mock Accounts: `user`/`user` and `admin`/`admin`)*
