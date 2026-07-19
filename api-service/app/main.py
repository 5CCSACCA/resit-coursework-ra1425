import os
from typing import List

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session

from . import auth, models, schemas
from .database import Base, engine, get_db
from prometheus_fastapi_instrumentator import Instrumentator

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Transcription SaaS - API & auth service")
Instrumentator().instrument(app).expose(app)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

TRANSCRIPTION_SERVICE_URL = os.getenv(
    "TRANSCRIPTION_SERVICE_URL", "http://transcription-service:8001"
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    try:
        payload = auth.decode_access_token(token)
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/register", response_model=schemas.UserOut)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        email=payload.email, hashed_password=auth.hash_password(payload.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = auth.create_access_token({"sub": str(user.id), "role": user.role})
    return schemas.Token(access_token=token)

@app.post("/transcribe", response_model=schemas.JobOut)
async def transcribe(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    job = models.Job(user_id=current_user.id, filename=file.filename, status="processing")
    db.add(job)
    db.commit()
    db.refresh(job)

    audio_bytes = await file.read()

    async with httpx.AsyncClient(timeout=300) as client:
        try:
            response = await client.post(
                f"{TRANSCRIPTION_SERVICE_URL}/transcribe",
                files={"file": (file.filename, audio_bytes, file.content_type)},
            )
        except httpx.HTTPError:
            job.status = "failed"
            db.commit()
            raise HTTPException(status_code=502, detail="Transcription service unreachable")

    if response.status_code != 200:
        job.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail="Transcription service error")

    result = response.json()
    transcript = models.Transcript(
        job_id=job.id,
        text=result["text"],
        language=result.get("language"),
        duration_seconds=result.get("duration_seconds"),
    )
    db.add(transcript)
    job.status = "completed"
    db.commit()
    db.refresh(job)
    return job


@app.get("/jobs", response_model=List[schemas.JobOut])
def list_jobs(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    return (
        db.query(models.Job)
        .filter(models.Job.user_id == current_user.id)
        .order_by(models.Job.created_at.desc())
        .all()
    )


@app.get("/jobs/{job_id}", response_model=schemas.JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    job = (
        db.query(models.Job)
        .filter(models.Job.id == job_id, models.Job.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/jobs/{job_id}/transcript", response_model=schemas.TranscriptOut)
def get_transcript(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    job = (
        db.query(models.Job)
        .filter(models.Job.id == job_id, models.Job.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    transcript = (
        db.query(models.Transcript).filter(models.Transcript.job_id == job.id).first()
    )
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not ready yet")
    return transcript