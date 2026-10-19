# Demo reuse plan

What the Hindi demo (FastAPI + Next.js) gives us, and what happens to each part in the MVP.

## Keep (move into the new structure, light changes)
| Demo piece | Where it goes | Notes |
|---|---|---|
| `app/auth.py` PBKDF2 hashing, HS256 JWT in an httpOnly cookie, `sid` claim | `app/core/security.py` + `app/deps.py` | Same cookie model. Add password-reset tokens, `last_login_at`, role `admin` (was `assessor`). |
| `services/protection.py` signed URLs, PlayGrant, session binding, key-fetch limit, SecurityEvent log | `app/services/protection.py` | Grant binds to `DialogueAttempt` + `Segment` instead of `Attempt` + plan index. Rate limiter stays in-memory per process (documented); fine for one Hetzner box. |
| `routers/media.py` HLS playlist rewrite + AES key endpoint | `app/routers/media.py` | Reads from the new storage layer (S3) instead of bundle/DB. |
| `services/media_pipeline.py` `package_hls()` (ffmpeg AES-128 HLS + chime) | `app/services/media_pipeline.py` | Input is downloaded audio from the CSV URL, not TTS. Output uploaded to S3. |
| `services/stt.py` provider switch, Whisper verbose_json with word timestamps | `app/services/stt/` | Becomes a provider interface; Groq `whisper-large-v3-turbo` default, fallback model from env, language hint `tl`/`en`. |
| `marking.py` ideas: structured JSON output, validation + one retry, "quote must be a substring" check, delivery metrics from word timestamps | `app/services/scoring/` | Rewritten to SCORING_BRIEF: MU-based accuracy, occurrence-based LQ/Fluency, code applies penalties. |
| `processing.py` "visible failure, never silent" pattern | `app/worker/` | Becomes a DB-backed job queue + worker process with retries. |
| Admin attempt review + override-with-note | `app/routers/admin_*` | Override now targets individual deductions (AdminReview), totals recomputed. |
| Frontend `lib/api.ts`, `components/ui.tsx`, `AppShell`, attempt player mic check / level meter / HLS playback / MediaRecorder logic | `frontend/src` | Player restructured into the NAATI flow (Info 1, Info 2, one page per segment, summary, submit). |
| `next.config.ts` same-origin `/api` rewrite + security headers | unchanged | Same-origin is what makes cookie-bound media work. |

## Refactor
- **Models**: replace `Activity`/`Attempt`/`SegmentResponse`/`Marking` with the client data model (`docs/DATA_MODEL.md`):
  Language, LanguagePair, Topic, Dialogue, Segment, MeaningUnit, DialogueAttempt, MockTestAttempt, SegmentAttempt,
  the three error tables, AIScoringRun, AdminReview, etc. UUID PKs, timestamps, Alembic.
- **Config**: `config/ccl.yaml` (Hindi voices, repeat deductions, demo scaling to 35 segments) is replaced by
  `ccl.yaml` (test flow) + `scoring.yaml` (penalties/thresholds from SCORING_BRIEF). `rubric.yaml` (severity points)
  is dropped; the brief uses fixed per-error penalties instead.
- **Settings**: drop Vercel/Neon/`/tmp` branches; Postgres URL required; add S3, Stripe, email, Gemini, Groq.
- **Storage**: `StoredFile` (bytes in Postgres) and bundled `data/media` are replaced by S3 via boto3 with a
  configurable endpoint (AWS now, Hetzner Object Storage later). A local-filesystem backend stays for tests/dev.
- **Background work**: FastAPI `BackgroundTasks` + `process_stale` serverless safety net replaced by a worker.

## Delete
- Hindi content (`content/dialogues/*.yaml`), bundled `backend/data/media/**` audio, `seed.py`, `seeding.py`
  (TTS seeding, synthetic student answers), `edge-tts` dependency.
- Vercel: `vercel.json`, `.vercelignore`, `POSTGRES_URL`/`VERCEL` handling.
- Content studio (paste-script-to-TTS) in `routers/admin.py` and `admin/content` page: replaced by CSV import.
- Heuristic marker and browser speech-recognition fallback (`lib/browserStt.ts`): MVP needs real STT; dev uses a
  clearly labelled mock provider.
- Demo-only pages: community, questions, sessions, videos (ComingSoon), LanguagePicker (single pair at launch).
- `smoke_test.py`, `e2e_test.py`: replaced by a pytest suite.
