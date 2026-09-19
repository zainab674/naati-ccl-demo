# Benchmark NAATI CCL Prep: demo

A proof of concept for a NAATI CCL practice platform (Hindi ↔ English). See [SPEC.md](SPEC.md) for scope.

- **Exam-realistic dialogue player.** Segments play once. There's one repeat, a chime, then auto-recording. Plays are enforced on the server, so refresh, back and a second tab can't get a replay.
- **AI marking.** Speech-to-text, then Claude marks against a structured rubric with quotes from the student's own words. Points, repeats and pass/fail are plain code.
- **Content protection.** AES-128 encrypted HLS, signed 5-minute URLs bound to the login session, rate limiting with an anomaly flag, and a protection panel.
- **Content studio.** Paste a script to get TTS voices, the chime and encrypted audio, published to the library.

## Run locally

Backend (Python 3.12):

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # macOS/Linux: .venv/bin/pip
cp .env.example .env                            # add keys (optional, see below)
.venv/Scripts/python seed.py                    # builds DB + all audio (~1 min, needs internet for TTS)
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

Frontend (Node 20+):

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000  (proxies /api to :8000)
```

Accounts (password `demo1234`): `priya@example.com` (student with history), `arjun@example.com` (new student), `assessor@example.com`.

API smoke test (22 checks: play limits, signed URLs, session binding, marking, roles): `.venv/Scripts/python smoke_test.py`

## Keys

| Key | What it turns on | Without it |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude marks each segment with rubric categories, severity and a quote | Static rule-based marker. It only catches numbers and large omissions |
| `GROQ_API_KEY` or `OPENAI_API_KEY` | Whisper transcribes the student's real recording | The segment's sample answer is used as the transcript, labelled "demo mode" in the UI |

**Re-run `seed.py` after adding keys** so Priya's seeded attempts are re-marked by Claude.

## Where to change things

| What | Where |
|---|---|
| CCL rules: 45/90, pass 63, min 29, repeats, response window | `backend/config/ccl.yaml` |
| Marking rubric, severity points, filler words | `backend/config/rubric.yaml` |
| Marking prompt and schema | `backend/app/services/marking.py` |
| STT provider | `backend/app/services/stt.py` |
| Dialogue content | `backend/content/dialogues/*.yaml` or the Content studio |

## Deploy (one URL)

`Dockerfile` builds a single container. Next.js serves the public port and proxies `/api` to FastAPI inside the container. It seeds itself on first start. Deploy it to Render, Railway or Fly with a persistent volume on `/app/backend/data`, and set `SECRET_KEY`, `COOKIE_SECURE=true` and the API keys as environment variables. For Postgres, set `DATABASE_URL`.

## Known demo limits

- Rate limiting is in-memory (single instance). Use Redis in production.
- Background marking uses FastAPI background tasks. Use a job queue in production.
- Per-user audio watermarking is explained on the protection page but not built.
- TTS uses Microsoft Edge's free voices. Use a licensed TTS provider for production content.
