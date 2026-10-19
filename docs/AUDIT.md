# Adversarial audit of the MVP build

Audited against `docs/MVP_SPEC.md` and `docs/SCORING_BRIEF.md`, from the diff `c979abd..017b1da` (37 commits), the
test files and the running app. Raw tool output is in `docs/audit/`. Fixes are commits `bcab453`..`1a5d115`.

**Proof labels** used throughout:

| Label | Meaning |
|---|---|
| **real** | an automated test exercises the actual code path against real Postgres / real ffmpeg / real crypto, and asserts the outcome |
| **stubbed** | a test exists, but the part that matters most is faked (Stripe API, Groq, Gemini, S3, SMTP, URL fetches, the microphone) |
| **manual** | only checked by hand in the browser during the build (no automated test; frontend has no test suite) |
| **none** | nothing checks it |

Nothing labelled "stubbed" or "manual" is verified in the sense of the brief: it is consistent with my own stubs,
nothing more.

## 1. Traceability matrix

### MVP_SPEC

| # | Requirement | Implemented in | Proof | Label |
|---|---|---|---|---|
| 1.1 | Sign up, login, logout (email + password) | `routers/auth.py` | `test_auth.py::test_signup_login_logout`, `test_signup_validation` | real |
| 1.2 | Password reset by email | `routers/auth.py` `forgot_password`/`reset_password` | `test_password_reset_flow`, `test_reset_invalidates_old_sessions` (console email provider) | real (delivery: stubbed) |
| 1.3 | Roles student / admin | `models/users.py`, `deps.require_admin` | `test_security.py::test_every_admin_route_rejects_students` (33 routes) | real |
| 1.4 | Paid plan gates mock tests and lessons; free intro dialogue/lessons | `deps.ensure_access`, `routers/student.py start`, `routers/courses.py lesson` | `test_access.py`, `test_player.py::test_library_shows_locked_and_free`, `test_mock_test_attempt`, `test_courses.py` | real |
| 2.1 | Home: offer, products, FAQ, sign-up | `frontend/src/app/page.tsx`, `content/site_content.json` | `test_foundation.py::test_public_content_defaults_and_override` (API only) | manual |
| 2.2 | Self-Study and Coaching pages: description, included, price, reviews, CTA, Enrol -> checkout | `components/PlanLanding.tsx`, `app/enrol/[plan]` | none for the pages; checkout API in `test_billing.py` | manual |
| 2.3 | Pricing; Coaching shows "Contact us" | `app/pricing`, `routers/billing.plan_dict` | `test_public_plans_and_checkout_guard` | real (API), manual (page) |
| 2.4 | Content from config/records, not JSX | `routers/public.py`, `site_content.json` | `test_public_content_defaults_and_override` | real |
| 2.5 | Mobile friendly, SEO, Terms and Privacy | Next metadata, `sitemap.ts`, `robots.ts`, legal pages | checked at 375 px in the browser once | manual |
| 3.1 | Stripe Checkout with price IDs from env | `services/billing.create_checkout` | `test_checkout_creates_session` (fake Stripe client) | stubbed |
| 3.2 | Webhook updates status (checkout completed, subscription updated/deleted, payment failed) | `services/billing.handle_event` | `test_subscription_lifecycle`, `test_one_off_payment_mode`, `test_out_of_order_subscription_events_keep_access`; signatures computed locally with the real `stripe` verifier | stubbed (no event from Stripe itself) |
| 3.3 | Admin sees payment/subscription status | `routers/admin_students.student` | `test_students_list_and_detail` | real |
| 4.1 | Dashboard: average score, available, recent, continue, quick start | `routers/student.dashboard`, `(app)/dashboard` | `test_player.py::test_dashboard`, `test_e2e` | real (API), manual (page) |
| 4.2 | Hidden slot for webinars | `upcoming_webinars: []` | none | none |
| 5.1 | Library by topic and difficulty | `routers/student.dialogues` | `test_library_shows_locked_and_free` (topic filter only) | real (topic), none (difficulty filter) |
| 5.2 | Status not started / in progress / completed + best score | `_dialogue_progress` | partially in `test_library_shows_locked_and_free` (not_started only) | none for in_progress/completed/best |
| 6.1 | Information 1, Information 2 with sound test and mic record/playback | `app/attempt/[id]/page.tsx` | browser walk-through with a synthetic microphone stream | manual |
| 6.2 | One page per segment: instructions, waveform, source audio, record, attempt counter, Start, Finish Attempt | same | browser walk-through; waveform/plays APIs in `test_player.py` | manual (UI), real (API) |
| 6.3 | Recording starts after the chime; precise timestamps | `onEnded` -> `startRecording`, `timing` stored | timestamps stored: `test_chunked_recording_upload_and_playback`; chime -> record only seen in the browser | manual |
| 6.4 | Repeat tracked (RepeatEvent) | `attempts.register_play` | `test_play_limits_repeats_and_protected_media` | real |
| 6.5 | Autosave and resume | `/step`, `state.current`, start returns the in-progress attempt | `test_practice_flow_resume_and_no_answer_leak` | real (API), manual (reload in browser) |
| 6.6 | Summary of answered/skipped, then Submit | summary step, `attempts.submit` | `test_submit_marks_skipped_and_queues_scoring`, `test_skip_is_final` | real (API) |
| 6.7 | HLS encrypted, short-lived signed URLs bound to session; no transcripts during attempt | `routers/media.py`, `services/protection.py`, `attempts.state` | `test_play_limits_repeats_and_protected_media` (session mismatch, tampered signature, key served), `test_media_ingest.py` (real ffmpeg AES-128 packaging) | real |
| 6.8 | Mock test = 2 dialogues | `start_mock`, `_apply_mock` | `test_mock_test_attempt`, `test_mock_tests` | real |
| 7.1 | STT on each recording with word timestamps (Groq Whisper) | `services/stt.py` | request shape and fallback against a fake OpenAI client; no call ever reached Groq | stubbed |
| 7.2 | Programmatic start delay > 5 s, pauses > 3 s | `scoring/timing.py` | `test_timing.py` on synthesised tones/silence | real (synthetic audio only) |
| 7.3 | AI compares MUs vs interpretation, structured JSON | `scoring/evaluator.py`, `prompts/evaluate_segment_v1.md` | `test_evaluator.py` with a scripted LLM; Gemini never called | stubbed |
| 7.4 | Penalties from config: -1 per MU, -0.5 per LQ / fluency | `scoring/engine.py`, `config/scoring.yaml` | `test_engine.py`, `test_engine_properties.py` (hypothesis), mutation 31/46 killed, 13 of 15 survivors equivalent | real |
| 7.5 | Pronunciation flagged, not deducted (switch) | `engine.item_deduction`, `records.store_evaluation` | `test_pronunciation_is_review_only_by_default` | real |
| 7.6 | Every model call in AIScoringRun | `transcribe.py`, `pipeline.score_one` | `test_practice_attempt_scored_end_to_end`, `test_evaluator_outage_retries_then_fails_visibly` | real (with mock providers) |
| 7.7 | Background job with retries; status updated | `jobs.py`, `pipeline.py`, `worker.py` | pipeline tests via `jobs.run_until_empty`; `worker.py` main loop: 0% coverage | real (job logic), none (worker process) |
| 7.8 | Low confidence -> admin review | `pipeline.score_one` | `test_low_confidence_flags_review` | real |
| 8.1 | Total /90, Pass/Fail (63, 29 per dialogue) | `records.recalc_*`, `engine.mock_score` | `test_mock_test_totals_and_pass_rules`, `test_pass_rules`, `test_e2e` | real |
| 8.2 | Breakdown by criterion | `services/results.py` | `test_results_payload` | real (API), manual (page) |
| 8.3 | Per segment: transcript, errors with explanation and suggested version, playback | `results.segment_result`, `SegmentResultCard` | `test_results_payload` | real (API), manual (page) |
| 8.4 | Attempt history | `results.attempt_results.history` | `test_results_payload` (one attempt) | real |
| 9.1 | Two courses, lessons with video + sanitised HTML | `routers/courses.py`, `services/html.py` | `test_courses.py`, `test_courses_and_lessons`, sanitiser tests | real (content not provided: none) |
| 9.2 | Completion tracking, free/paid lessons | `courses.complete` | `test_course_gating_and_completion` | real |
| 10.1 | Dialogue CSV import (format in spec) with URLs to S3 | `imports/dialogues.py` | `test_import_dialogues.py` (URL checks faked) | real (parsing), stubbed (URL reachability) |
| 10.2 | Course CSV import | `imports/courses.py` | `test_import_courses.py` | real |
| 10.3 | Dry-run report: missing fields, enums, unreachable URLs, duplicate keys | `parse()` | `test_dry_run_reports_errors` | real (URL part stubbed) |
| 10.4 | Idempotent re-import | `commit()` | `test_commit_and_idempotent_reimport`, `test_course_commit_sanitises_and_is_idempotent` | real |
| 10.5 | Fetch audio from URL and run the HLS pipeline | `media_ingest.py` | `test_ingest_packages_encrypted_hls` (download faked, ffmpeg real, local storage instead of S3) | stubbed (download, S3) |
| 10.6 | Edit, publish, hide; HTML editor | `admin_content.py`, admin pages | `test_admin_content.py` | real (API), manual (pages) |
| 10.7 | Downloadable template and sample | `admin_imports.template` | `test_templates_download`, `test_sample_file_validates_structure` | real |
| 11.1 | Student list with search/filter | `admin_students.students` | `test_students_list_and_detail` | real |
| 11.2 | Open any attempt: recordings, transcript, AI output, every deduction | `admin_students.attempt_detail`, `runs` | `test_attempt_detail_has_ai_output_and_recording_access` | real |
| 11.3 | Override with note; totals recalculate | `admin_students.override`, `records.recalc_all` | `test_override_recalculates_totals`, `test_weight_change_after_scoring_does_not_rescore_old_attempts` | real |
| 12.1 | Welcome, receipt, password reset, results ready emails | `emails/templates.py`, `services/email.py` | `test_email.py` (SMTP/Resend faked), `test_e2e` asserts all three journey emails logged | stubbed (delivery) |
| CSV | Column-exact formats | `REQUIRED`/`OPTIONAL` lists | `test_missing_column_and_encoding` | real |
| — | Not-in-MVP items absent; data model allows new LOTEs without schema change | `Language`/`LanguagePair` rows | `test_language_pair_rules` (adds Hindi with no migration) | real |

### SCORING_BRIEF

| # | Rule | Implemented in | Proof | Label |
|---|---|---|---|---|
| S1 | AI identifies, platform calculates; never ask the model for a score | `evaluator.Evaluation` has no score fields; `records` writes deductions | `test_schema_has_no_scores` | real |
| S2 | Rules changeable without changing the prompt | `config/scoring.yaml` | `test_penalties_come_from_config` | real |
| S3 | Accuracy per MU: omission, insertion, distortion, -1 each | `MU_RESULTS`, `engine` | `test_brief_penalties`, `test_segment_and_dialogue_totals_example` | real |
| S4 | Assess meaning, not word-for-word | prompt text | none: only a real model on real answers can show this | none |
| S5 | LQ types incl. register and sentence structure, -0.5 per occurrence | prompt, `LQ_TYPES`, `engine` | `test_brief_penalties` (arithmetic); classification untested | real (arithmetic), none (classification) |
| S6 | Pronunciation review-only for MVP | as 7.5 | as 7.5 | real |
| S7 | Pause > 3 s and delay > 5 s measured by code | `timing.py` | `test_start_delay_and_pause_from_audio` (synthetic) | real (synthetic only) |
| S8 | Hesitation: distinguish natural speech from genuine hesitation | candidates to the AI; AI decides | none | none |
| S9 | Self-correction | prompt; `FL_TYPES` | arithmetic only | none (detection) |
| S10 | AI returns which MU, error type, explanation; suggested version | `MUItem`, `LanguageItem` | `test_retry_when_a_meaning_unit_is_missing` | stubbed |
| S11 | Admin-approved MUs are authoritative; AI MU suggestions only | `suggest_meaning_units` never saves | `test_suggest_meaning_units_mock` | real (mock provider) |
| S12 | Dialogue max 45, total 90, pass >= 63 and >= 29 per dialogue, floor 0 | `engine`, `scoring.yaml` | `test_pass_rules`, `test_floor_at_zero`, hypothesis `test_mock_pass_rule`, `test_score_is_bounded` | real |

### What the matrix says

- The **arithmetic** of scoring (S1-S3, S6, S12, 7.4) is the best-proven part of the system: unit, property and
  mutation tests.
- The **judgement** parts (S4, S5 classification, S8, S9, 7.3) have **no** evidence. They depend on Gemini and Whisper
  behaving well on Filipino and Taglish answers, which no test touches.
- **Every external integration** (Stripe, Groq, Gemini, S3, SMTP/Resend, URL downloads) is stubbed.
- **The frontend has no automated tests.** The test player, the most important screen, was walked through once with
  a synthetic microphone. Safari/iOS were never exercised.

## 2. Defects

### Confirmed and fixed (each written as a failing test first: `tests/test_audit_regressions.py`)

| ID | Severity | Where (fix) | Failing scenario before the fix | Commit |
|---|---|---|---|---|
| A1 | Score shown to a student is wrong | `services/scoring/pipeline.py:152` (`finalize`) | Gemini rejects a segment (non-retryable). The segment is marked Failed but contributes 0 deductions, so the dialogue is shown as **43/45 Pass** and counts in the dashboard average | `bcab453` |
| A2 | Data is lost + score wrong | `services/scoring/records.py:27` (`clear_results`), `pipeline.py:197`, `pipeline.py:158` | Teacher adds a Grammar error, then clicks Re-score: the teacher's error is deleted, the segment stays "reviewed" so it leaves the queue, and the student gets a second "results ready" email | `19a6617` |
| A3 | Score shown to a student is wrong (silently) | `models/scoring.py:35`, `records.py:109` | Admin changes a Meaning Unit's weight from 1 to 3 for future use. Any later recalculation of an old attempt (e.g. an override) re-scores it with the new weight: 41.5 -> **39.5** with no record of why | `900f4d4` |
| A4 | Payment or access is wrong | `services/billing.py:179` (`_is_stale`) | Stripe delivers `customer.subscription.updated` (active) then an older one (past_due): the paying student is set to **Expired** and locked out. Same for a stale `invoice.payment_failed` | `bc78c78` |
| A5 | Payment is wrong | `routers/billing.py:42` | An active subscriber opens the pricing page again and clicks Enrol: a **second subscription** is created and billed | `ceb4ad5` |
| A6 | Score shown is wrong (wrong audio scored) | `services/attempts.py:199` (`_parts_prefix`), `frontend/src/lib/recorder.ts` | Student presses Repeat while a part upload of the discarded take is retrying; the late retry overwrites the same part index of the new take, so the scored audio mixes two takes (test: submitted audio was `OLD-ANSWER`) | `ff969c8` |
| A7 | Security (dependency) | `frontend/package.json` | `next@16.3.5` is in the range of critical advisories (RCE in `next/og` ImageResponse, SSRF in image optimisation, cache poisoning). Upgraded to 16.4.2 | `1a5d115` |

### Confirmed, not fixed (lower severity or needs a decision)

| ID | Severity | Where | Scenario | Why not fixed |
|---|---|---|---|---|
| B1 | Payment/access (policy) | `billing.py:115` `"past_due": EXPIRED` | One failed renewal locks the student out immediately, during Stripe's own retry window | Business decision: keep access while Stripe retries? Spec only says "updates subscription_status" |
| B2 | Security | `services/ratelimit.py:12` | Limits are in memory per process; production runs 2 API workers, so each limit is effectively doubled and resets on restart | Acceptable for one server; Redis or a Postgres-backed limiter if it matters |
| B3 | Security (admin-only) | `media_ingest.py:33`, `imports/common.py:86` | CSV URLs are fetched with redirects allowed; an admin (or a stolen admin session) can make the server fetch internal addresses (SSRF) | Admin-trusted input; fix by refusing private/link-local IPs |
| B4 | Score wrong (wasted play) | `attempts.py:175` | A play is counted before the audio loads; a network failure during loading uses up the repeat | NAATI-like strictness vs fairness: needs a decision |
| B5 | Score wrong (mid-test) | `media_ingest.py:104` | Re-processing a dialogue's audio deletes the old HLS package while a student may be mid-attempt on it; their next play 404s | Rare; fix by deleting old packages only when no attempt is in progress |
| B6 | Score wrong (unverified) | `timing.py:72` (`abs_floor_db=-48`, `margin 14 dB`) | Tuned on synthetic tones. A quiet speaker could have words below the threshold, producing false "Pause" deductions | Needs hand-labelled real recordings (section 4) |
| B7 | Score wrong (unverified) | `pipeline.py:54` | Whisper often "hears" text in silence ("Thank you."); a silent answer is then evaluated as content instead of "no speech" | Needs real recordings; consider `no_speech_prob` and VAD together |
| B8 | Data lost (unverified) | `recorder.ts` + `attempts.complete_recording` | Safari records `audio/mp4`; joining 3-second MediaRecorder chunks may not give a decodable file | Needs a real Safari/iOS test |
| B9 | Access (low) | `routers/auth.py:81` | 10 failed logins per minute for an email locks that account's login for a minute; anyone can trigger it | Low impact; standard trade-off |
| B10 | Cosmetic / dead code | `engine.py:28` | `ItemResult.needs_review` is computed but never read; review flags come from the stored rows | Harmless |
| B11 | Content exposure (policy) | `results.py:16` | After submission the source transcript is shown with feedback; a student can collect dialogue scripts | Config switch exists (`results.show_source_transcript`); Benchmark decides |

## 3. Tool results (raw output in `docs/audit/`)

| Tool | Result | Notes |
|---|---|---|
| pytest + pytest-cov | 157 passed after fixes; 90% line coverage | Uncovered where it matters: `ai/llm.py` 55% (Gemini/Anthropic/OpenAI code never run), `storage.py` 54% (S3 never run), `worker.py` 0%, real URL download in `media_ingest.py` never run |
| Mutation testing on `engine.py` | 31/46 killed (67%); 15 survived | mutmut does not run on native Windows, so `scripts/mutate.py` (AST mutations) was used. 13 survivors are equivalent (rounding digits on multiples of 0.25; defaults for config keys that are always present). 2 real: untested dialogue number in fail reasons (test added) and dead `needs_review` (B10) |
| hypothesis (5 invariants, ~1,700 cases) | all hold | score in [0, max]; adding an error never raises a score; totals = sum of items; override wins; pass rule |
| alembic downgrade base -> upgrade head -> check | clean; "No new upgrade operations detected" | run before the three fix migrations; the new migrations were each downgraded and re-applied once |
| bandit | 7 Low, 0 Medium, 0 High | subprocess with list arguments (ffmpeg); two string literals mistaken for passwords |
| semgrep (p/python, p/owasp-top-ten) | 227 rules, 118 files, 0 findings | |
| pip-audit | No known vulnerabilities | |
| npm audit | before: 8 (1 critical, 7 high); after A7: 5 high | remaining: `braces` via `eslint-config-next` (dev/lint only; npm's fix downgrades to the Next 14 config) |
| Secrets: gitleaks | **not run**: not installed on this machine | substitute below |
| Secrets: detect-secrets over every diff in all 37 commits, plus a regex scan | 0 findings | also `tests/test_security.py::test_no_secrets_committed` on tracked files |

Also noticed on this machine (not the project): `NODE_TLS_REJECT_UNAUTHORIZED=0` is set in the environment, which
disables TLS certificate checks for every Node process.

## 4. Scoring validity plan (to run with Benchmark)

The question is not "does the code apply -1 correctly" (proven) but "does the AI find the same errors a teacher
finds, consistently". Nothing below can be answered without real answers and real teachers.

### 4.1 Samples

| Set | Size | Composition | Purpose |
|---|---|---|---|
| Pilot (the planned 10 samples) | 10 segment answers | mixed directions | smoke test only: is anything wildly off. Too small for any statistic |
| Segment set | **≥ 120 segment answers** | ≥ 20 different students, both directions (EN>FIL, FIL>EN), all difficulty levels, deliberately including weak answers, Taglish, noisy rooms, quiet voices, one-word answers and silence | agreement per criterion, MU confusion matrix, VAD accuracy. 120 gives a 95% CI of roughly ±0.08 on an ICC around 0.8 |
| Mock set | **≥ 40 full mock attempts** (80 dialogues), aiming for ~20 passes and ~20 fails by teacher judgement | real candidates or Benchmark's students | pass/fail sensitivity/specificity; dialogue-level Bland-Altman |
| Retest set | 30 segment answers from the segment set | | test-retest: each run 5 times through Gemini (and STT) |

### 4.2 Marking protocol

- Two Benchmark teachers mark every sample **blind**: independently, without seeing the AI's output or each other's.
- For every answer they record what the platform records: each MU as correct / omission / distortion, each
  insertion, each LQ error with its type, each hesitation/self-correction, and their judgement of start delay and
  pauses. Use the same CSV columns as `scripts/teacher_samples_template.csv`, extended with per-MU labels.
- Disagreements between the two teachers are kept (they set the ceiling); a third teacher adjudicates to build a
  reference marking.

### 4.3 Analyses and acceptance criteria (proposed; Benchmark to confirm)

| Analysis | Measure | Accept if |
|---|---|---|
| Teacher vs teacher | ICC(2,1) per criterion and total; weighted kappa on per-segment deductions | establishes the ceiling; the AI is not expected to beat it |
| AI vs reference, per criterion | ICC(2,1), weighted (quadratic) kappa on deductions in 0.5 steps | AI-reference agreement ≥ 0.9 × teacher-teacher agreement, for each criterion |
| Dialogue score | Bland-Altman: mean difference (bias) and 95% limits of agreement, AI vs reference, out of 45 | bias within ±1.5 points; limits of agreement within ±5 points |
| Meaning Units | 3x3 confusion matrix (correct / omission / distortion) + insertion precision/recall | recall of errors (omission or distortion) ≥ 0.85; correct MUs wrongly penalised ≤ 10% |
| Language quality | precision and recall of LQ errors (type-agnostic, then by type) | precision ≥ 0.8 (false deductions are what students notice) |
| Pass/fail at 63 (and ≥ 29 per dialogue) | sensitivity and specificity of AI Pass vs reference Pass, mock set | both ≥ 0.85; report every borderline case (reference total 58-68) individually |
| Test-retest | SD of segment deductions across 5 runs; pass/fail flips across runs | segment SD ≤ 0.5; no pass/fail flip on the mock set; otherwise fix temperature/seed or take the median of 3 runs |
| Timing (VAD) | hand-label speech onset and every silence > 2 s in Praat or Audacity on the segment set | start-delay error median ≤ 0.3 s, 95th percentile ≤ 1 s; Pause precision ≥ 0.9, recall ≥ 0.8 |
| STT | word error rate of Whisper vs a teacher's transcript, per direction | report only; scoring errors should be traced to STT vs evaluator before tuning the prompt |

`scripts/eval_against_teacher.py` already produces per-criterion AI vs teacher deductions for the segment set; the
statistics above need its CSV output plus the per-MU labels.

### 4.4 Does -1 per Meaning Unit push typical students to 0?

Simulated with the actual engine and config (`config/scoring.yaml`), 600 runs per row; "other errors" = language +
fluency occurrences per segment at -0.5 each:

| Dialogue size | MUs conveyed | Other errors / segment | Mean score /45 | P(score = 0) | P(≥ 29) |
|---|---|---|---|---|---|
| 12 segments × 3 = 36 MUs | 85% | 1.0 | 33.6 | 0.00 | 0.97 |
| 14 × 4 = 56 MUs | 85% | 1.0 | 29.8 | 0.00 | 0.62 |
| 16 × 5 = 80 MUs | 85% | 1.0 | 25.0 | 0.00 | **0.14** |
| 14 × 4 = 56 MUs | 70% | 1.0 | 21.1 | 0.00 | 0.02 |
| 16 × 5 = 80 MUs | 50% | 1.0 | 0.8 | 0.75 | 0.00 |

- **The floor is not the problem**: a student reaches 0 only when they convey about half the meaning or less.
- **The real problem is that a dialogue's difficulty is set by how finely it was split into Meaning Units.** The
  same student passes a 36-MU dialogue 97% of the time and an 80-MU dialogue 14% of the time. The brief applies -1
  per MU with a fixed 45-point budget, so Benchmark either needs an MU-splitting guideline that keeps dialogues
  comparable (e.g. a target MU count per dialogue) or a normalisation rule. This is a scoring-design decision, not
  a code fix, and it should be settled with the real MU counts of the 36 ready dialogues and the validation data.

## 5. What only outside evidence can settle

| Question | Who/what settles it | Acceptance criterion |
|---|---|---|
| Does the AI mark like a teacher? | Two Benchmark teachers, blind (section 4) | the criteria in 4.3 |
| Are the MU-count effects acceptable? | Benchmark, with the MU counts of the 36 dialogues | a written rule (target MU range or normalisation) applied to every dialogue |
| Do payments work end to end? | Stripe's dashboard event log in test mode, then one live AUD transaction, refunded | every event in DEPLOY_HETZNER.md §6 delivered with HTTP 200; access unlocks within 10 s of payment; a cancelled subscription locks access at period end; a failed-then-retried payment ends Active |
| Does the deployment guide work? | Someone other than the author, on a fresh Hetzner server, using only `docs/DEPLOY_HETZNER.md` | site live over HTTPS, admin login, a CSV import with audio processed, a mock test scored, a backup restored, in one sitting, with every deviation from the guide written down |
| Does recording work on real devices? | Real Chrome (Windows, Android), Safari (macOS, iOS), Firefox, with real microphones | on each: equipment check passes, a 30 s answer uploads, the joined file decodes with ffmpeg and the transcript matches what was said |
| Does the S3 path work? | The real bucket (AWS or Hetzner Object Storage) | import 1 dialogue, play it in an attempt, play back the recording, delete-on-reprocess leaves no orphaned objects |
| Is Gemini's output stable and affordable? | Real Gemini calls on the retest set | test-retest criteria in 4.3; cost per scored mock test recorded |
| Do students understand and trust the feedback? | A pilot with 10-20 Benchmark students over two weeks | ≥ 90% of started mock tests submitted; upload failures < 1%; every "the score is wrong" complaint reviewed against teacher marking |
| Is the player close enough to the NAATI practice test? | Benchmark staff who have sat it, side by side | written sign-off or a list of differences to fix (attempt counter, repeats, skip) |
| Are the legal pages, reviews and prices final? | Benchmark (and their lawyer) | Terms/Privacy no longer marked draft; reviews are real and permitted; prices come from Stripe |
