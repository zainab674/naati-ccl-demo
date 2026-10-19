# CCL Platform (Benchmark Education): instructions for Claude Code

You are building the **MVP of a NAATI CCL practice and mock test platform** for Benchmark Education (Australia).
This repo already contains a working **demo** (FastAPI backend + Next.js frontend, Hindi). Your job is to turn it
into the production MVP described in `docs/MVP_SPEC.md`, following `docs/BUILD_PLAN.md` step by step.

## Read first, every session
1. `docs/MVP_SPEC.md`: what to build (12 modules). This is the source of truth for scope.
2. `docs/SCORING_BRIEF.md`: the client's scoring rules. Follow them exactly.
3. `docs/DATA_MODEL.md`: the client's database structure.
4. `docs/BUILD_PLAN.md`: the ordered task list with checkboxes. Work on the first unchecked task, tick it when done
   and verified, then continue. Append a one-line note under "Progress log" at the bottom of BUILD_PLAN.md.

## How to work
- Work autonomously through BUILD_PLAN.md. Do not stop to ask unless a task is genuinely blocked (missing key, missing
  client content). If blocked, write the question under "Open questions" in BUILD_PLAN.md, stub it cleanly, and move on.
- Reuse the demo where it helps (auth, protected audio/HLS, marking pipeline, admin attempt review), but refactor freely.
  The demo's Hindi content, TTS seeding and Vercel-specific code are not needed in production.
- Small, focused commits with clear messages after each completed task. Never push or force-push unless told to.
- After each module: run the backend tests and `npm run build` for the frontend. Do not tick a task with failing builds.
- Never commit secrets. All keys go in `.env` (gitignored); keep `.env.example` up to date.
- Do not invent content: no fake reviews, testimonials, prices or student data in production pages. Use clearly
  marked placeholders ("Sample review, replace before launch") only in seed/dev data.
- Keep everything configurable: scoring penalties, pass marks, timing thresholds and AI model names live in config
  files or env vars, never hard-coded in logic.

## Stack (decided with the client)
- Frontend: **Next.js (React) + TypeScript + Tailwind** (existing `frontend/`).
- Backend: **Python FastAPI** (existing `backend/`), SQLAlchemy 2 + **Alembic** migrations.
- Database: **PostgreSQL** (production on a Hetzner server). Local dev via docker compose.
- Storage: S3-compatible object storage (AWS S3 now, possibly Hetzner Object Storage later). Use boto3 with a
  configurable endpoint so both work.
- Payments: **Stripe** (Checkout + webhooks).
- Email: transactional only, via an SMTP/Resend-style provider behind a small interface.
- Speech-to-text: **Groq Whisper Large V3 Turbo** (fallback `whisper-large-v3`), behind a provider interface.
- AI evaluation: **Google Gemini Flash-Lite** (configurable model name), behind a provider interface, structured JSON
  output validated with Pydantic. Keep the existing Anthropic/OpenAI providers as optional alternatives.
- Deployment: Docker images + docker compose on Hetzner (Caddy or Nginx for HTTPS).

## Core rule of the scoring engine
**AI identifies and classifies errors. Code applies the penalties.** Never ask a model for a score.
Timing (start delay, long pauses) is measured from audio by code, not by the model.

## Launch language
English <-> **Filipino (Tagalog)**. The data model must support adding more LOTEs later with no schema changes.
