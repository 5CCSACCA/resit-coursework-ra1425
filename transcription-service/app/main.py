import os
import tempfile
import time
import librosa
import torch

from peft import PeftModel
from transformers import WhisperProcessor, WhisperForConditionalGeneration
from fastapi import FastAPI, File, UploadFile
from faster_whisper import WhisperModel
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Transcription SaaS")
Instrumentator().instrument(app).expose(app)

MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

# Scottish-accent specialized model: base Whisper + LoRA adapter via
# transformers. Kept separate from the faster-whisper model above,
# LoRA adapters aren't compatible with the CTranslate2 format
# faster-whisper uses, so this path uses a different library entirely.
SCOTTISH_MODEL_NAME = "openai/whisper-base"
scottish_processor = WhisperProcessor.from_pretrained(SCOTTISH_MODEL_NAME)
_scottish_base = WhisperForConditionalGeneration.from_pretrained(SCOTTISH_MODEL_NAME)
scottish_model = PeftModel.from_pretrained(_scottish_base, "lora-adapter")
scottish_model.eval()

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

@app.post("/transcribe/scottish")
async def transcribe_scottish(file: UploadFile = File(...)):
    start = time.time()
    suffix = os.path.splitext(file.filename or "")[1] or ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        audio, _ = librosa.load(tmp_path, sr=16000)
        inputs = scottish_processor(audio, sampling_rate=16000, return_tensors="pt")
        with torch.no_grad():
            generated_ids = scottish_model.generate(
                inputs.input_features, language="en", task="transcribe", max_new_tokens=225
            )
        text = scottish_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    finally:
        os.remove(tmp_path)

    return {
        "text": text.strip(),
        "language": "en",
        "duration_seconds": round(time.time() - start, 2),
        "model": "scottish-whisper-lora",
    }