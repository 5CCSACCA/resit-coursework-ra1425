# Transcription SaaS

A speech-to-text transcription platform built on OpenAI's Whisper, deployed as
a set of Docker microservices. Includes a general-purpose transcription
endpoint and a second endpoint fine-tuned for Scottish-accented English.

## Quick start

```bash
docker compose build
docker compose up
```

Both models (the general Whisper base model and the Scottish LoRA adapter)
download automatically during the build step, no manual setup required.

Once running, the API is available at `http://localhost:8000`. Interactive
API docs (Swagger UI) are at `http://localhost:8000/docs`.

## Services

| Service | Description | Reachable from host? |
|---|---|---|
| `api-service` | Auth, rate limiting, job tracking, proxies to transcription-service | Yes, port 8000 |
| `transcription-service` | Runs Whisper (general + Scottish fine-tuned) | No, internal only |
| `postgres` | Stores users, jobs, transcripts | No, internal only |
| `prometheus` | Scrapes metrics from both services | No, internal only |
| `grafana` | Dashboards, reads from Prometheus | Yes, port 3000 |

## Example usage

A sample audio file is included at `samples/sample.wav` for testing.

**Register a user:**
```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```
Expected response:
```json
{"id": 1, "email": "test@example.com", "role": "user"}
```

**Log in:**
```bash
curl -X POST http://localhost:8000/login \
  -F "username=test@example.com" -F "password=password123"
```
Expected response:
```json
{"access_token": "eyJ...", "token_type": "bearer"}
```

**Transcribe audio (general):**
```bash
TOKEN="paste your access_token here"
curl -X POST http://localhost:8000/transcribe \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@samples/sample.wav;type=audio/wav"
```
Expected response:
```json
{"id": 1, "status": "completed", "filename": "sample.wav", "created_at": "..."}
```

**Transcribe audio (Scottish-accent fine-tuned model):**
```bash
curl -X POST http://localhost:8000/transcribe/scottish \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@samples/sample.wav;type=audio/wav"
```

**List your jobs:**
```bash
curl http://localhost:8000/jobs -H "Authorization: Bearer $TOKEN"
```

**Get a transcript:**
```bash
curl http://localhost:8000/jobs/1/transcript -H "Authorization: Bearer $TOKEN"
```

## Monitoring

Grafana is available at `http://localhost:3000` (login: `admin` / `admin`).
The "Transcription SaaS Overview" dashboard loads automatically and shows
request rate, error rate, and p95 latency.

## Rate limits

| Endpoint | Limit |
|---|---|
| `/register` | 5/minute |
| `/login` | 10/minute |
| `/transcribe`, `/transcribe/scottish` | 20/minute |

## Constraints

`transcription-service` is limited to 4 vCPUs and 16GB RAM directly in
`docker-compose.yml`, matching the coursework's hardware constraint. This has
been tested under concurrent load, see the report's Costs section for
details.

## Running tests

```bash
cd api-service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-test.txt
python -m pytest -v
```
## Testing evidence

`testing-evidence/cpu-load-test-capped.txt` contains raw output from
concurrent load testing described in the report's Costs and Architecture
sections: 5 concurrent `/transcribe` and 3 concurrent `/transcribe/scottish`
requests, all returning `200`, with `transcription-service` capped to 4
vCPUs / 16GB and CPU usage staying under that limit throughout. Kept here
as supporting evidence for those figures.

## Architecture

See the full report for the architecture diagram, model fine-tuning
methodology, cost analysis, and sustainability calculation.