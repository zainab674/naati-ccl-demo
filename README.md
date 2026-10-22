# CCL Platform (Benchmark Education)

NAATI CCL practice and mock test platform for English paired with Filipino, Hindi, Mandarin, Punjabi, Arabic, Nepali
or Vietnamese. Students practise dialogues in the official test flow, record their interpretation segment by segment
and get an estimated score out of 90 with feedback on every deduction. They also have courses and a learning hub
(ebooks, glossaries, worksheets, audio, articles, links). Admins import content by CSV, enrol students by hand or by
CSV (e.g. demo accounts), review scoring and override deductions.

- Scope: [docs/MVP_SPEC.md](docs/MVP_SPEC.md) · scoring rules: [docs/SCORING_BRIEF.md](docs/SCORING_BRIEF.md) ·
  data model: [docs/DATA_MODEL.md](docs/DATA_MODEL.md) · build log and open questions: [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md)
- Deploy: [docs/DEPLOY_HETZNER.md](docs/DEPLOY_HETZNER.md) · security: [docs/SECURITY.md](docs/SECURITY.md)

## Architecture

| Part | Tech | Notes |
|---|---|---|
| `frontend/` | Next.js 16, React 19, TypeScript, Tailwind 4 | public site, student app, test player, admin |
| `backend/` | FastAPI, SQLAlchemy 2, Alembic, PostgreSQL | REST API under `/api` |
| worker | `python -m app.worker` | Postgres-backed job queue: media ingest and scoring |
| storage | S3-compatible (AWS S3 / Hetzner / MinIO) | encrypted HLS audio, waveforms, recordings, CSVs |
| providers | Groq Whisper Large V3 Turbo (STT), Gemini Flash-Lite (evaluation), Stripe, SMTP/Resend | each behind an interface, mock/console fallbacks for development |

**Scoring rule:** the AI identifies and classifies errors; code applies the penalties.

```
recording ─▶ STT (word timestamps) ─▶ timing analysis in code (start delay > 5 s, pauses > 3 s)
          ─▶ AI evaluator (per Meaning Unit: correct / omission / distortion; insertions; language quality; hesitation,
             self-correction) ─▶ deduction engine (config/scoring.yaml) ─▶ segment, dialogue (/45), mock (/90), pass/fail
```

Rules and penalties live in `backend/config/scoring.yaml` and `backend/config/ccl.yaml`; the evaluator prompt in
`backend/app/prompts/`; per-language guidance in the `language_scoring_configs` table (seeded from
`backend/app/seed_languages.py`; adding a language is data only).

## Run locally

### With Docker

```bash
cp .env.example .env
docker compose up --build
```

Frontend http://localhost:3000 · API docs http://localhost:8000/api/docs · MinIO console http://localhost:9001.
The admin account comes from `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `.env`.

### Without Docker

Needs Python 3.12, Node 20, PostgreSQL 15+ (and ffmpeg on the PATH, or the bundled `imageio-ffmpeg` binary is used).

```bash
cp .env.example .env        # set DATABASE_URL / TEST_DATABASE_URL; STORAGE_BACKEND=local is easiest
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt          # Windows: .venv\Scripts\pip
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed --dev                      # --dev adds clearly marked placeholder reviews
.venv/bin/uvicorn app.main:app --reload --port 8000
.venv/bin/python -m app.worker                          # second terminal: scoring and media jobs
cd ../frontend && npm install && npm run dev            # third terminal
```

Without `GROQ_API_KEY` / `GEMINI_API_KEY` scoring runs in a labelled mock mode (the result pages say so); without
Stripe keys plans show "Contact us"; emails print to the backend log (`EMAIL_PROVIDER=console`).

## Content

Admin → CSV import accepts `dialogues.csv` (one row per Meaning Unit) and `courses.csv` (one row per lesson); the
formats are in [docs/MVP_SPEC.md](docs/MVP_SPEC.md#csv-formats) and templates/samples download from the import page.
Every upload is validated first (dry run); committing is idempotent by key. Dialogue audio is downloaded from the CSV
URLs, encrypted and packaged by the worker, then the dialogue can be published.

Admin → Learning hub manages study resources; files (PDF, EPUB, Office, MP3/M4A/WAV, MP4, images, up to
`RESOURCE_MAX_MB`) are stored privately and served only to signed-in students with access.
Admin → Students → Add student / Bulk enrol creates accounts without Stripe, with Trial/Active access and an optional
end date; students get a set-password email, or the admin sets a password for demo accounts.

## Demo data (development only)

```bash
cd backend && .venv/Scripts/python -m app.demo_data          # add DEMO content, students and scored attempts
cd backend && .venv/Scripts/python -m app.demo_data --reset  # remove it again
```

Adds 9 practice dialogues across all seven languages (synthetic audio through the real encrypted-audio pipeline),
2 mock tests, 2 courses with chapters, 4 learning-hub resources (one PDF) and 4 students (`demo.active`,
`demo.trial`, `demo.free`, `demo.expired` @example.com; password `DEMO_PASSWORD` in `.env.example`) with attempts
scored by the real pipeline using stand-ins for speech-to-text and the AI (no API calls). Everything is marked DEMO;
the translations were not reviewed by a credentialed translator. Refuses to run when `ENVIRONMENT=production`.

## Tests and checks

```bash
make check            # or: bash scripts/check.sh   (ruff + pytest, eslint + next build)
```

Backend tests run against a real PostgreSQL database (`TEST_DATABASE_URL`, migrated once per run) and real ffmpeg;
AI, STT, Stripe and email providers are stubbed. `tests/test_e2e.py` walks the whole student journey.

Comparing AI scoring with teacher marking (the 10-sample check):

```bash
cd backend && .venv/bin/python -m scripts.eval_against_teacher samples.csv --out report.csv
```

See `scripts/teacher_samples_template.csv` for the input format.

## Deploy

Docker Compose on one Hetzner server with Caddy for HTTPS: `docker compose -f docker-compose.prod.yml up -d --build`.
Full steps (DNS, object storage, Stripe webhook, backups, updates) in [docs/DEPLOY_HETZNER.md](docs/DEPLOY_HETZNER.md).
