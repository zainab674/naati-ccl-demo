# Build plan (work top to bottom; tick each box only when built AND verified)

Milestones map to client payments. Keep the app runnable after every task.

## M0. Foundation
- [x] 0.1 Read the existing demo (`README.md`, `SPEC.md`, `backend/app`, `frontend/src`). Write a short
      `docs/DEMO_REUSE.md`: what to keep, refactor, delete.
- [x] 0.2 `docker-compose.yml` for local dev: postgres, backend, frontend (+ worker, + redis if used).
      `.env.example` with every variable (DB, SECRET_KEY, S3_*, GROQ_API_KEY, GEMINI_API_KEY, STRIPE_*, EMAIL_*, APP_URL).
- [x] 0.3 Switch backend to PostgreSQL + Alembic. Remove Vercel/SQLite-in-/tmp hacks and TTS seeding from the prod path.
- [x] 0.4 Implement the data model in `docs/DATA_MODEL.md` (models + first migration). Seed: English, Filipino,
      LanguagePair EN<->FIL, a few topics, admin user from env, Filipino LanguageScoringConfig.
- [x] 0.5 Config: move CCL rules + penalties to `backend/config/ccl.yaml` / `scoring.yaml` matching SCORING_BRIEF.md
      (MU -1, LQ -0.5, Fluency -0.5, pause 3 s, delay 5 s, pass 63, min 29, dialogue max 45, pronunciation review-only).
- [x] 0.6 Test setup: pytest with a Postgres test DB; frontend `npm run build` + lint pass. Add a CI-style `make check`.

## M1. Accounts, payments, public site
- [x] 1.1 Auth: sign up, login, logout, password reset (token email), roles, httpOnly cookie sessions (reuse demo JWT).
- [x] 1.2 Access control helper: `requires_active_plan`, free-content flags respected.
- [x] 1.3 Stripe: Plan table, Checkout session endpoint, webhook (signature verified, idempotent),
      subscription_status updates, customer portal link. Test with Stripe test mode + CLI.
- [x] 1.4 Email service (provider interface + SMTP/Resend impl + console impl for dev). Templates: welcome, receipt,
      password reset, results ready. EmailLog.
- [x] 1.5 Public site: Home (offer, products, FAQ, sign-up), Self-Study and Coaching landing pages (description,
      included, price, reviews, CTA, Enrol -> checkout), pricing section, Terms, Privacy. Content from SiteContent /
      a content JSON, placeholders clearly marked. Responsive, SEO meta.

## M2. Content and admin import
- [x] 2.1 Admin shell + admin auth guard.
- [x] 2.2 Dialogue CSV import (format in MVP_SPEC.md): upload -> dry-run validation report (missing fields, enums,
      URL HEAD checks, duplicate keys) -> commit. Idempotent by dialogue_key/segment_no/mu_no. ImportJob records.
      Downloadable template + sample.
- [x] 2.3 Media ingest: on commit, download audio from URL, run the protected HLS pipeline from the demo, store in S3
      (boto3, configurable endpoint). Store waveform image. Background job with status in ImportJob.
- [x] 2.4 Course CSV import (course_key, lesson rows) with the same dry-run/commit flow.
- [x] 2.5 Admin content screens: list/edit/publish/hide dialogues (segments, MUs editable), courses and lessons with a
      sanitised HTML editor.
- [x] 2.6 Optional helper: "Suggest Meaning Units" button per segment (AI suggests, admin edits/approves).

## M3. Student experience
- [x] 3.1 Student dashboard: average score, available dialogues/mock tests, recent attempts, continue unfinished,
      quick start.
- [x] 3.2 Dialogue library: filters by topic/difficulty, status + best score per dialogue.
- [x] 3.3 Mock test player matching the NAATI practice test flow: Info 1, Info 2 (equipment check: test sound,
      mic record/playback), one page per segment (instructions left; waveform, source audio, record answer, attempt
      counter, Start, Finish Attempt right), chime then recording, precise timestamps captured, repeat tracking,
      autosave + resume, final summary of answered/skipped, Submit. Mock test = 2 dialogues.
- [x] 3.4 Recording upload: chunk-safe upload to S3, linked to SegmentAttempt; protected playback for student/admin.
- [x] 3.5 Courses: course list, lesson page (video + HTML), completion tracking, free/paid gating.

## M4. AI scoring, results, review
- [x] 4.1 STT provider interface; Groq Whisper Large V3 Turbo impl with word timestamps, language hint `tl`;
      fallback model via env. Store transcript + words.
- [x] 4.2 Audio timing analysis (code): speech start vs recording start (> 5 s), internal pauses (> 3 s), filler
      detection candidates from LanguageScoringConfig.hesitation_markers.
- [x] 4.3 LLM evaluator interface; Gemini Flash-Lite impl with JSON schema output; Pydantic validation; prompt
      versioned in `backend/app/prompts/`; Filipino guidance from LanguageScoringConfig; evaluates per MU and
      occurrence-based errors; returns explanations + suggested versions; never returns scores.
- [x] 4.4 Deduction engine (pure functions, unit-tested): apply config penalties, merge AI + programmatic events,
      pronunciation as review flag, segment/dialogue/attempt totals, floor at 0, Pass/Fail per brief.
- [x] 4.5 Background worker: score each SegmentAttempt after submit, retries, AIScoringRun logging, statuses,
      low-confidence -> needs review. Send "results ready" email when the attempt completes.
- [x] 4.6 Results page: total /90, Pass/Fail, breakdown by criterion, per-segment transcript, errors with
      explanations and suggested versions, recording playback, attempt history.
- [x] 4.7 Admin students list + attempt review: recordings, transcript, AI output, every deduction, override with
      note (AdminReview) and recalculation; subscription status visible.
- [x] 4.8 Accuracy check script: `scripts/eval_against_teacher.py` that runs N teacher-marked answers through the
      pipeline and prints AI vs teacher deductions per criterion (for the 10-sample test with the client).

## M5. Launch
- [x] 5.1 Production Dockerfiles, `docker-compose.prod.yml`, Caddy/Nginx HTTPS, health checks, logging.
- [x] 5.2 `docs/DEPLOY_HETZNER.md`: server setup, Postgres, backups, env, Stripe webhook URL, DNS.
- [x] 5.3 Security pass: rate limits, CSRF/cookie flags, upload limits, HTML sanitisation, secrets audit,
      admin-only routes, signed media URLs.
- [x] 5.4 End-to-end test: sign up -> pay (test mode) -> course lesson -> full mock test -> scoring -> results ->
      admin override -> emails logged.
- [x] 5.5 Update README with run, test and deploy instructions.

## M6. Scope additions (client request, 2026-10-20)
- [x] 6.1 Manual student enrolment (MVP_SPEC module 13): admin creates students (set password or emailed invite),
      grants Active/Trial access with an optional end date (expires automatically), bulk CSV enrolment with dry run,
      edit/extend/revoke/deactivate/resend invite, grant history. Stripe purchases take over from manual grants.
- [x] 6.2 Additional languages (module 14): seed Hindi, Mandarin, Punjabi, Arabic, Nepali, Vietnamese + EN pairs +
      starting LanguageScoringConfig per language; student language choice (sign-up, account); library, mock tests,
      courses filtered by language; Course.language_pair_id; admin language filters; RTL-safe text; no
      Filipino-only wording left in shared UI.
- [x] 6.3 Learning hub (module 15): Resource model + migration, private file upload/serving, admin CRUD, student hub
      with type/language filters and free/paid gating.

## Open questions (write here when blocked, then continue)
- Number of courses at launch (spec assumes 2).
- Who sets up the Hetzner server (spec assumes we provide compose + deploy guide).
- Landing page content editable in admin, or file-based for MVP (spec: SiteContent records, simple admin form if time).
- Dialogue count at launch (36 ready, 50 planned): import handles any number.

- Stripe test keys + price IDs (STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_SELF_STUDY): needed to run
  checkout end-to-end with `stripe listen`. Webhook handling is verified with locally signed test events.
- Plan model: monthly subscription or one-off payment for a fixed period? Both are supported
  (STRIPE_CHECKOUT_MODE=subscription|payment); one-off currently unlocks until an admin/expiry changes it.
- Plan prices: shown from the Stripe Price (or an admin-set display text); no prices are hard-coded.
- Public copy: backend/content/site_content.json holds factual default copy; reviews are empty until Benchmark supplies
  real, permitted reviews; Terms/Privacy are marked DRAFT for Benchmark's legal review. Coaching contact email needed
  (SiteContent "coaching".contact_email).
- S3: the boto3 backend (configurable endpoint for AWS/Hetzner/MinIO) is written but has only been exercised
  through the local storage backend here; verify against the real bucket once credentials exist.
- Player repeats (updated 2026-10-20 from the client's Loom videos): Start again after Finish attempt repeats a segment;
  1 repeat per dialogue (ccl.yaml max_repeats_per_dialogue), only the last attempt kept. Further repeats are blocked;
  should they instead be allowed with a penalty (scoring.yaml penalties.repeat)?
- Camera: shown as a preview only, never recorded; camera.required is false so students without a webcam can practise.
  Should the camera be required, or video recorded for teacher review?
- Navigation: Previous/Next let a student go back to an earlier segment and answer it (or use the repeat there), as
  the NAATI test's buttons suggest. Confirm this matches the real exam.
- Repeat penalty: SCORING_BRIEF.md sets none, so repeats are tracked but cost 0 (scoring.yaml penalties.repeat).
- AI keys: GROQ_API_KEY and GEMINI_API_KEY are needed to run real STT/evaluation. Providers are tested with stubs;
  the 10-sample teacher comparison (4.8) is the real accuracy check. Gemini model name is GEMINI_MODEL.
- Scoring design (from the audit, docs/AUDIT.md §4.4): with a fixed 45-point budget and -1 per MU, a dialogue's
  difficulty depends on how many MUs it was split into (same student: 97% pass chance at 36 MUs, 14% at 80).
  Needs an MU-splitting guideline or a normalisation rule.
- Access during Stripe's payment retry window (past_due): keep or remove? Currently removed immediately.
- A play that fails to load still uses up the repeat. Keep (exam strictness) or refund the play?

Scope additions (2026-10-20), questions for Nipun:
- Teachers: is "teacher" the same as admin (full access, as built), or a separate role that can only enrol students and
  review attempts (no content editing)?
- Manual access: Trial and Active unlock the same content. Should a teacher-granted Trial be limited (e.g. a number of
  mock tests)? Should an end date be required for manual grants?
- Bulk enrolment skips existing emails. Should a re-upload instead update their access (e.g. extend a whole class)?
- Evaluator guidance for Hindi, Mandarin, Punjabi, Arabic, Nepali and Vietnamese (app/seed_languages.py, then the
  language_scoring_configs table) is a starting draft. A Benchmark teacher for each language should review the grammar,
  register and hesitation-marker lists, and the 10-sample teacher comparison (4.8) should be repeated per language.
- Arabic: which varieties are accepted (MSA only, or dialects such as Levantine/Egyptian)? Currently both are accepted.
  Punjabi: Gurmukhi and Shahmukhi transcripts are both accepted.
- Whisper is noticeably less accurate for Punjabi and Nepali than for the other languages; check transcripts on real
  student recordings before relying on scores in those two languages.
- Content: dialogues, mock tests and the exam preparation course are needed for each new language. The public copy now
  lists all seven languages; confirm they should be advertised before their content is ready.
- Pricing: one price for every language (as built), or per-language plans?
- Learning hub: which ebooks/resources exist, and may students download them, or should they be view-only (a
  view-only PDF can still be saved by a determined user; watermarking with the student's email is possible later)?
  Which resources are free? Max file size is 50 MB (RESOURCE_MAX_MB).

## Progress log
- 2026-10-19 0.1: read the demo, wrote docs/DEMO_REUSE.md (keep auth/HLS protection/STT/player; replace models, config, storage, worker; delete Hindi/TTS/Vercel).
- 2026-10-19 0.2: docker-compose.yml (postgres:17, minio, backend, worker, frontend) + root .env.example. Validated with `docker compose config`; could not run the stack here (Docker Desktop's WSL VM would not start), dev/tests used a local Postgres on :5433 instead.
- 2026-10-19 0.3: Postgres-only settings (psycopg 3), Alembic wired to app settings; Vercel/SQLite/bundled-media/TTS seeding removed.
- 2026-10-19 0.4: all DATA_MODEL.md tables + MockTest, Job queue, StripeEvent, PasswordResetToken; initial migration; idempotent `python -m app.seed`.
- 2026-10-19 0.5: config/scoring.yaml (penalties, 3 s pause, 5 s delay, 63/29/45/90, pronunciation review-only) and config/ccl.yaml (test flow).
- 2026-10-19 0.6: pytest on a real Postgres test DB (migrated once, truncated + seeded per test), ruff, `make check` / scripts/check.sh (backend lint+tests, frontend lint+build).
- 2026-10-19 1.1: signup/login/logout/forgot/reset (1 h single-use hashed tokens, session_version invalidates old cookies), /me, rate-limited; login/signup/forgot/reset pages; demo pages removed pending M3 rebuild.
- 2026-10-19 1.2: deps.requires_active_plan / ensure_access(is_free) / is_locked (Active+Trial unlock, admins always), 402 for locked content; unit tests.
- 2026-10-19 1.3: Plan/Subscription/Payment/StripeEvent; /api/public/plans, /billing/checkout, /billing/portal, /billing/status, signed + idempotent /stripe/webhook (checkout, subscription created/updated/deleted, invoice paid/failed); receipt email; account + billing success pages. Not run against live Stripe test mode (no keys yet, see Open questions).
- 2026-10-19 1.4: EmailProvider interface (console/SMTP/Resend), HTML+text templates (welcome, receipt, password reset, results ready), every send in EmailLog, failures logged not raised; provider tests with fakes.
- 2026-10-19 1.5: public Home, Self-Study and Coaching landing pages, Pricing, Terms, Privacy, Enrol -> signup -> Stripe Checkout; content from SiteContent with JSON defaults (no invented reviews/prices), server-rendered with SEO metadata, sitemap.xml, robots.txt; checked desktop + mobile in the browser.
- 2026-10-19 2.1: /api/admin router with require_admin on every route (401/403 tested), /admin shell (client guard redirects non-admins) and overview page.
- 2026-10-19 2.2: dialogues.csv import: upload -> dry-run report (missing fields, enums, language codes, consistency across repeated rows, duplicate keys, URL HEAD/range-GET checks) -> commit; idempotent upsert by dialogue_key/segment_no/mu_no (missing items deactivated, version bump on change); ImportJob history; template + sample downloads; admin import UI. S3/local storage service added.
- 2026-10-19 2.3: Postgres job queue (SKIP LOCKED, retries with backoff, failure hooks) + `python -m app.worker`; per-segment ingest job: download (size-capped) -> chime -> AES-128 HLS (demo pipeline) -> storage; waveform from CSV URL or drawn by ffmpeg; unchanged audio skipped by hash; ImportJob progress/failures. Tested with real ffmpeg.
- 2026-10-19 2.4: courses.csv import with the same dry-run/commit flow (ImportJob), lesson HTML sanitised with nh3 allow-list (warns when content was stripped), idempotent by course_key/lesson_no, missing lessons archived.
- 2026-10-19 2.5: admin dialogue list/editor (details, publish/hide with readiness checks, segment transcript, MU table add/remove/renumber, re-process audio, waveform preview), mock test definitions (2 dialogues, same pair), course + lesson editor with sanitised HTML and live server-side preview. Checked in the browser.
- 2026-10-19 2.6: LLM provider layer (Gemini default, Anthropic Opus 5.5 / OpenAI optional, mock; strict JSON schema output, typed retryable errors); 'Suggest with AI' per segment fills the MU editor for the admin to edit and save (never auto-saved); prompt in app/prompts/suggest_meaning_units_v1.md.
- 2026-10-19 3.1: student API (dashboard, library, mock tests, attempts with resume, server-counted plays + RepeatEvents, session-bound HLS media ported from the demo, chunked recording upload, submit) with 8 player tests; dashboard page (averages, availability, continue unfinished, quick start, recent attempts, free-plan banner; webinars slot left empty) + My attempts page.
- 2026-10-19 3.2: dialogue library with topic/difficulty filters, status (not started / in progress / completed), best score, free/locked badges, start/continue; mock tests list page.
- 2026-10-19 3.3: player /attempt/[id]: Information 1, Information 2 (test tone + mic record/playback), one page per segment (instructions left; protected waveform, no-seek source audio, answer area, plays/recording counters, Start, Finish Attempt, Repeat, Skip) with chime -> auto-record, client timestamps (chime end, record start/stop, first speech), server-side autosave/resume, summary of answered/skipped, Submit. Walked through in the browser with real encrypted HLS (mic stubbed: the browser pane blocks capture).
- 2026-10-19 3.4: recordings uploaded in 3 s parts while speaking (idempotent part PUTs, retries/backoff, retry-saving button), joined server-side into storage, linked to the SegmentAttempt; owner/admin-only playback endpoint. Verified the joined WebM decodes (12.2 s).
- 2026-10-19 3.5: courses API (published courses/lessons, free = course or lesson flag, 402 on paid lessons, idempotent completion) + course list with progress, course outline, lesson page (embed/mp4 video, sanitised HTML, mark complete, previous/next with lock).
- 2026-10-19 4.1: STT interface; Groq whisper-large-v3-turbo (verbose_json, word+segment timestamps, language hint from Language.stt_code, e.g. tl) with STT_FALLBACK_MODEL retry; recordings normalised to 16 kHz FLAC; transcript, words, provider/model and an AIScoringRun(kind=stt) stored per segment; labelled mock provider for keyless dev.
- 2026-10-19 4.2: timing.py: energy VAD (adaptive noise floor, hangover) on decoded 16 kHz PCM, speech start incl. chime->recorder gap, StartDelay > 5 s and Pause > 3 s from scoring.yaml, Whisper word timings as fallback, filler candidates from LanguageScoringConfig markers (multi-word too). Tested on synthesised audio.
- 2026-10-19 4.3: evaluator with versioned prompt app/prompts/evaluate_segment_v1.md (brief's MU / insertion / LQ / fluency rules, meaning not wording, pauses left to code), Filipino guidance from LanguageScoringConfig, Pydantic schema with no score fields, every MU exactly once (corrective retry), quotes checked against the transcript, explanation + suggested version per item; Gemini via get_llm (Anthropic/OpenAI optional), mock text-match evaluator for dev.
- 2026-10-19 4.4: engine.py pure functions (config penalties, MU weight switch, insertion, pronunciation review-only switch, admin override per item, floor 0, dialogue pass >= Dialogue.passing_score, mock pass >= 63 total and every dialogue >= its minimum) with 11 unit tests incl. the brief's example; records.py stores AI + audio-analysis events as error rows with platform-set deductions and recalculates segment/dialogue/mock totals (exercised by the 4.5 pipeline tests).
- 2026-10-19 4.5: score_segment worker job: STT -> VAD timing -> evaluator -> error records -> engine; retryable provider errors retried (4 tries, backoff), final failure marks the segment Failed + needs review; every STT/evaluation call logged in AIScoringRun; skipped or silent answers = all MUs omitted (silent flagged for review); low AI/STT confidence, poor transcript or unmatched quotes -> needs review; dialogue/mock finalised under row locks once all segments are done; results-ready email once. Fixed: alembic fileConfig was disabling app loggers.
- 2026-10-19 4.6: results API + page: estimated total /90 (or /45), Pass/Fail with reasons, criterion breakdown per attempt and dialogue, per segment: source (config switch), what we heard, recording playback, feedback, every MU/insertion/LQ/fluency item with explanation, suggested version and deduction, review badges; live polling while scoring; attempt history; dev-mode banner when providers are mocked. Checked in the browser.
- 2026-10-19 4.7: admin students list (search, subscription filter, attempts, average) and detail (subscriptions, payments, lessons, attempts); review queue (needs review / failed); attempt review with recordings, transcripts, word timings, every deduction, raw AI runs (request/raw/processed), per-item override with required note -> AdminReview -> segment/dialogue/mock recalculation, teacher-added errors, mark reviewed (also completes a failed segment scored by hand), re-score.
- 2026-10-19 4.8: scripts/eval_against_teacher.py (+ teacher_samples_template.csv): runs teacher-marked answers (audio or transcript) through STT -> timing -> evaluator -> engine without DB writes, prints AI vs teacher per criterion, mean |diff|, bias, exact/within-0.5 counts, optional per-sample CSV with the AI's errors. Needs real keys for a meaningful run.
- 2026-10-19 5.1: docker-compose.prod.yml (postgres, backend x2 uvicorn workers with migrations+seed on start, worker with graceful stop, Next.js standalone frontend, Caddy auto-HTTPS), deploy/Caddyfile (/api -> FastAPI, HSTS, 25 MB body cap, JSON logs), healthchecks on every service, rotated json-file logs, frontend multi-stage Dockerfile. Validated with docker compose config and a local standalone build; images not built here (Docker daemon unavailable on this machine).
- 2026-10-19 5.2: docs/DEPLOY_HETZNER.md (server + firewall, Docker, DNS, Hetzner/AWS object storage, .env table, start + first admin steps, Stripe live webhook URL/events/portal, backups with deploy/backup.sh + restore, updates, operations).
- 2026-10-19 5.3: security pass (docs/SECURITY.md): Origin check middleware for unsafe /api requests, security headers + no-store, API docs off in production, Secure cookies forced and long SECRET_KEY required in production, play and AI-suggestion rate limits, route-by-route admin authorisation test (33 routes), secrets scan test; existing upload limits, sanitisation, signed session-bound media reviewed.
- 2026-10-19 5.4: tests/test_e2e.py: admin creates a mock test -> student signs up (locked content) -> checkout + signed test-mode webhooks (checkout.session.completed, invoice.paid) -> lesson opened and completed -> full 2-dialogue mock test with real audio -> worker scores 4 segments -> results 86/90 Pass -> admin override -> 87/90 -> welcome, receipt and results emails logged. Stripe and AI providers are stubbed (no keys); the UI parts were checked separately in the browser.
- 2026-10-19 5.5: README rewritten (architecture, scoring flow, run with/without Docker, content import, tests, teacher comparison, deploy); frontend README; outdated demo SPEC.md removed.
- 2026-10-19 audit: docs/AUDIT.md (traceability matrix with real/stubbed/manual/none labels, defects, tool results, scoring validity plan, outside-evidence criteria). Fixed 7 confirmed defects with failing-first regression tests: inflated score on failed segments, re-score discarding teacher work, MU weight edits re-scoring old attempts, out-of-order Stripe events, double subscription, discarded-take audio overwriting the answer, Next.js critical advisories.
- 2026-10-20 6.1: manual enrolment: POST/PATCH /api/admin/students, access grants (Active/Trial/None, optional end date in APP_TIMEZONE, expires automatically via effective_status) recorded as manual Subscription rows, set-password invite email (ENROLMENT_INVITE_HOURS) or admin-set password, deactivate signs out, bulk CSV with dry run (existing emails skipped); a teacher-granted student can still buy, and Stripe then replaces the grant. 14 API tests. Admin UI (Add student, Bulk enrol, access/account cards, grant history) type-checked, linted and built; not clicked through in the browser (signing in as admin was blocked here).
- 2026-10-20 6.2: Hindi, Mandarin, Punjabi, Arabic, Nepali, Vietnamese seeded with English pairs, Whisper hints and draft evaluator guidance (app/seed_languages.py, teacher review pending); language at sign-up and in Account; library, mock tests, courses filtered by the student's language (switchable, or all); Course.language_pair_id (+ courses.csv lote_language, admin course editor); admin dialogue language filter; /api/public/languages; filler matching fixed for Indic vowel signs, Arabic and unspaced Chinese; Whisper language names mapped; bdi/dir=auto for right-to-left text; Filipino-only wording removed. 12 tests.
- 2026-10-20 6.3: learning hub: Resource model + migration (Ebook/Glossary/Worksheet/Audio/Video/Article/Link, optional language and topic, free/paid, Draft/Published/Archived); private file upload with extension allow-list checked against the first bytes and RESOURCE_MAX_MB (Caddy allows 110 MB on that route only); files served only through /api/resources/{id}/file with plan check, no-store, same-origin framing for the inline PDF viewer; articles sanitised; publish blocked until content matches the type; admin page and student hub with type/language filters. 9 tests.
- 2026-10-20 browser check (dev, test accounts on localhost, since deactivated): sign-up language list, library language switch (found and fixed a stale-response race on all filtered lists), hub list and inline PDF, admin Add student (Trial until 31 Dec, Arabic, invite) and the student access/account cards. Not checked: bulk-enrol modal, resource audio/video playback, Safari/iOS, a real Arabic transcript in the results view.
- 2026-10-20 CSV uploads: every CSV upload (dialogues, courses, bulk enrol) now has "Download CSV format" (header row) and "Download example" buttons (shared CsvFormatButtons); new students example file; tests check each example passes its own validation. Checked in the browser.
- 2026-10-20 player rebuilt to match the NAATI test in the client's Loom walkthrough: exam header, breadcrumb with page counter, title bar with Help, progress strip, Previous/Next; Information 2 example segment (sound, speak, Finish attempt, Play back) checking speakers, microphone and camera; webcam preview (never recorded) with red border while recording; source waveform with playhead and live microphone trace; Attempts counter; repeat = Start again after Finish attempt, 1 per dialogue (configurable), only the last attempt stored (earlier recording deleted) and scored; resume returns to the first unanswered segment. Backend tests for the repeat rule. Walked through in the browser with a synthetic mic/camera (the pane blocks real devices): example segment, a segment with real encrypted audio, a repeat, Start disabled after the repeat, server keeps only try2, summary, reload/resume, phone width.
