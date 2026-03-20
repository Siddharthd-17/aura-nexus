# Aura Nexus - Deployment Guide (Google Cloud Run)

Follow these steps to deploy Aura Nexus to a production environment on Google Cloud.

## 1. Prerequisites
- Google Cloud SDK (`gcloud`) installed.
- Docker installed and authenticated.
- A Google Cloud Project with Billing enabled.

## 2. Environment Variables
You must set your `GEMINI_API_KEY` in the Cloud Run environment.

## 3. Build & Deploy Commands

Run these commands from the project root:

```bash
# 1. Enable required services
gcloud services enable run.googleapis.com containerregistry.googleapis.com

# 2. Build and Push the image (using Cloud Build)
gcloud builds submit --tag gcr.io/[PROJECT_ID]/aura-nexus

# 3. Deploy to Cloud Run
gcloud run deploy aura-nexus \
  --image gcr.io/[PROJECT_ID]/aura-nexus \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --update-env-vars GEMINI_API_KEY=[YOUR_KEY]
```

## 4. Persistent Storage (Important)
Cloud Run filesystems are **ephemeral**. When the service restarts, `emergencies.db` and the `recordings/` folder will be reset.

### Recommendation for Production:
1.  **Database**: Use **Cloud SQL (PostgreSQL/MySQL)** instead of SQLite. Update the `DATABASE_URL` in `main.py`.
2.  **Audio Files**: Modify `main.py` to upload files to **Google Cloud Storage (GCS)** instead of the local `recordings/` folder.
3.  **Volume Mounts (Beta)**: Alternatively, use **Cloud Run Second Generation** to mount a GCS bucket as a local directory.

## 5. Local Testing
To test the container locally:
```bash
docker build -t aura-nexus .
docker run -p 8080:8080 -e GEMINI_API_KEY=[YOUR_KEY] aura-nexus
```
Access the app at `http://localhost:8080`.
