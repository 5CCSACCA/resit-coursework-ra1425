import os
import tempfile
import time

from fastapi import FastAPI, File, UploadFile
from faster_whisper import WhisperModel

app = FastAPI(title="Transcription SaaS")

MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_SIZE}

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    start = time.time()
    suffix = os.path.splitext(file.filename or "")[1] or ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        segments, info = model.transcribe(tmp_path)
        text = " ".join(segment.text.strip() for segment in segments)
    finally:
        os.remove(tmp_path)

    return {
        "text": text.strip(),
        "language": info.language,
        "duration_seconds": round(time.time() - start, 2),
    }