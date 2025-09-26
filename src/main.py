import uuid
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.worker import run_analysis_pipeline # Import our new worker function

app = FastAPI()

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IngestRequest(BaseModel):
    repo_url: str

# We will use a simple dictionary to track job statuses for now
job_statuses = {}

@app.post("/api/v1/ingest")
async def ingest_repository(request: IngestRequest, background_tasks: BackgroundTasks):
    # Generate a real, unique job ID
    job_id = str(uuid.uuid4())
    job_statuses[job_id] = "processing"

    print(f"Starting job {job_id} for repository: {request.repo_url}")

    # This is the magic line: it schedules our function to run in the background
    background_tasks.add_task(run_analysis_pipeline, request.repo_url)

    # Immediately return the job ID to the user
    return {"status": "processing_started", "job_id": job_id}

# A new endpoint to check the status of a job
@app.get("/api/v1/ingest/status/{job_id}")
async def get_ingest_status(job_id: str):
    # In a real app, our worker would update this status
    status = job_statuses.get(job_id, "not_found")
    return {"job_id": job_id, "status": status}