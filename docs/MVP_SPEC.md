# CCL Platform: MVP Scope (Phase 1)

Web-based CCL Practice and Mock Test Platform where students practise CCL dialogues, record their interpretations
segment by segment, complete mock tests, and receive AI-assisted estimated scores and detailed feedback.
Language pairs: English <-> Filipino, Hindi, Mandarin, Punjabi, Arabic, Nepali and Vietnamese (the six were added to
the MVP on 2026-10-20 at the client's request; Filipino was the original launch pair).

## 1. Accounts and Access
- Sign up, login, logout (email + password). Password reset by email.
- Roles: `student`, `admin`. Admins (teachers) can also enrol students by hand (module 13).
- Access control: only students with an active paid plan can open mock tests and course lessons
  (allow 1 free intro dialogue and the free intro course lesson(s) as configured).

## 2. Public Website and Landing Pages
- Home page: what the platform offers, products/services, FAQ, sign-up button.
- Product landing pages: Self-Study plan and Coaching plan. Each: description, what's included, price, customer
  reviews, call to action, Enrol button linked to Stripe checkout.
- Pricing section: Self-Study vs Coaching. Coaching shows "Contact us" until coaching booking exists (later phase).
- Content (text, FAQ, reviews, prices) comes from a config/content file or admin-editable records, not hard-coded JSX.
- Mobile friendly, SEO titles/descriptions, Terms and Privacy pages (required by Stripe).
- Student journey: Sign-up -> free intro course / free mock test -> paid plan -> exam prep course -> mock tests.

## 3. Payments
- Stripe Checkout for paid plans (plan/price IDs from env/config).
- Stripe webhook (`checkout.session.completed`, `customer.subscription.updated/deleted`, `invoice.payment_failed`)
  updates `subscription_status` (Active / Trial / Expired / Inactive). Access unlocks automatically.
- Admin sees each student's payment/subscription status.

## 4. Student Dashboard
- Average score from previous attempts.
- Available CCL dialogues / mock tests.
- Recently attempted dialogues.
- Continue an unfinished attempt.
- Quick start a new dialogue. (Upcoming webinars: later phase, leave a hidden slot.)

## 5. Dialogue Library
- Browse by language, topic and difficulty. Defaults to the student's chosen language.
- Status per dialogue: not started / in progress / completed (with best score).

## 6. Mock Test Player (exam simulation)
Must mirror the official NAATI practice test flow (assessmentq):
- Page 1: Information 1 (about the test).
- Page 2: Information 2 (audio and microphone equipment check: play test sound, record and play back).
- One page per segment (~14 per dialogue): left = instructions; right = segment waveform image, source audio player,
  answer recording, attempt counter, Start button, Finish Attempt button.
- Recording starts after the chime; capture precise timestamps (chime end, speech start) for fluency scoring.
- Must look like the NAATI online test (client Loom walkthrough, Oct 2026): header with the user, breadcrumb with a
  page counter (e.g. 3/19), page title with Help, a progress strip and Previous/Next at the bottom right; webcam
  preview (camera checked on Information 2, never recorded); live source and microphone waveforms; Attempts counter.
- Information 2 is an example segment: Start, speak after the sound, Finish attempt, Play back.
- Repeat rule as in the NAATI test: Finish attempt, then Start again; one segment repeat per dialogue without
  penalty (config); only the last attempt's recording is kept and scored. Repeat use tracked (RepeatEvent).
- Progress auto-saved; student can resume an unfinished attempt.
- Final page: summary of answered and skipped segments, then Submit.
- Audio protection from the demo stays: segmented/encrypted HLS, short-lived signed URLs bound to the session,
  dialogue transcripts/answer keys never sent to the client during an attempt.

## 7. AI Scoring Engine
Implements `docs/SCORING_BRIEF.md` exactly:
- STT on each recording (Groq Whisper, word timestamps).
- Programmatic audio/timing analysis: start delay > 5 s, pauses > 3 s (from timestamps / VAD), candidate hesitations.
- AI (Gemini Flash-Lite) compares source Meaning Units vs student interpretation and returns structured JSON:
  accuracy_completeness items (Correct / Omission / Distortion per Meaning Unit, plus Insertions),
  language_quality items (grammar, unidiomatic usage, register, sentence structure; pronunciation only as a review flag),
  fluency language events (hesitation, self-correction).
- Platform applies penalties from config: -1 per affected Meaning Unit, -0.5 per Language Quality / Fluency occurrence.
- Pronunciation: flagged for admin review, not auto-deducted (config switch).
- Store every model call in AIScoringRun (provider, model, prompt_version, request, raw response, parsed result, status).
- Scoring runs as a background job (queue/worker), with retries; segment and attempt `scoring_status` updated.
- Low confidence -> flagged for admin review.

## 8. Results and Feedback
- Total score out of 90, Pass/Fail (default 63 overall, min 29 per dialogue; from config / Dialogue record).
- Breakdown by Accuracy & Completeness, Language Quality, Fluency.
- Per segment: what was heard (transcript), each error with explanation and a suggested version, recording playback.
- Attempt history.

## 9. Courses
- Courses: "Introduction to CCL Test" and "Exam Preparation (Filipino to English)".
- Course -> Lessons; each lesson: video (placeholder or URL) + HTML text (sanitised).
- Lesson completion tracking. Free vs paid lessons flag.
- A course belongs to one language (e.g. exam preparation for Hindi) or to all languages (e.g. the introduction).

## 10. Admin Content Management
- **CSV bulk import for dialogues** (one or many per file): dialogues, segments, transcripts, Meaning Units,
  reference interpretations/answer keys, and **URLs** to audio and waveform files (hosted on S3). See CSV format below.
- **CSV bulk import for courses**: courses, lessons, video URLs, HTML text.
- Validation report before commit (dry run): missing fields, bad enums, unreachable URLs, duplicate keys.
  Import is idempotent (re-import updates by key, does not duplicate).
- On dialogue import, fetch audio from the URL and run the existing protected-media pipeline (HLS) so students never
  get the raw S3 link.
- Edit, publish, hide (Draft / Published / Archived) dialogues and courses. HTML editor for lesson text.

## 11. Admin Students and Score Review
- Student list: profile, subscription status, attempts, scores. Search/filter.
- Open any attempt: listen to recordings, see transcript, AI output and every deduction.
- Override a deduction with a note (AdminReview); totals recalculate.

## 12. Automatic Emails
- Welcome, payment receipt, password reset, results ready. HTML templates, sender from env.

## 13. Manual Student Enrolment (added 2026-10-20)
Teachers/admins create student accounts without Stripe, e.g. demo accounts for testing or students who paid offline.
- Create one student: name, email, language, access (Active / Trial / none) with an optional end date, a note.
- Either set a password directly (demo accounts) or email the student a "set your password" invite link.
- Bulk enrolment from a CSV (`first_name, last_name, email, language, access, access_until`) with a dry-run report.
- Edit a student later: extend, change or remove access, change language, resend the invite, deactivate the account.
- Manually granted access ends automatically on its end date. A later Stripe purchase takes over from a manual grant.
- Every manual grant is recorded (who, when, note) and shown on the student's admin page.

## 14. Additional Languages (added 2026-10-20)
Hindi, Mandarin, Punjabi, Arabic, Nepali and Vietnamese alongside Filipino, each paired with English.
- Each language has an STT language hint and evaluator guidance (grammar, register, hesitation markers) in
  LanguageScoringConfig, to be reviewed by Benchmark's teachers for that language.
- Students choose their language at sign-up (changeable in Account). Library, mock tests, courses and resources show
  that language by default; a student can switch to another language.
- Admin lists filter by language; CSV imports take the language code. Right-to-left text (Arabic) displays correctly.
- Adding a further language later is data only: Language + LanguagePair + LanguageScoringConfig rows.

## 15. Learning Hub (added 2026-10-20)
A library of study resources beyond courses: ebooks (PDF), glossaries, worksheets, audio, articles and external links.
- Resource: title, description, type, optional language and topic, one of: a file (stored privately), an article
  (sanitised HTML) or an external URL; free/paid flag; Draft/Published/Archived; sort order.
- Students browse by type and language; paid resources show as locked without an active plan. Files are served only
  through an authenticated endpoint, never as a public storage link.
- Admin: list, create, edit, upload/replace the file, publish/hide.

## Not in the MVP (later phases)
Webinars; 1-on-1 coaching booking + Zoom; email marketing campaigns; messaging students; coupons; sales/revenue
dashboard. Design the data model so these can be added without rework.

## CSV formats

### dialogues.csv (one row per Meaning Unit; dialogue/segment columns repeat)
| column | notes |
|---|---|
| dialogue_key | unique slug, used for idempotent updates |
| dialogue_title, topic, difficulty | difficulty: Easy / Intermediate / Difficult |
| lote_language | e.g. `fil` |
| description, instructions | optional |
| segment_no | 1..n |
| direction | `EN>LOTE` or `LOTE>EN` |
| speaker_label, speaker_role | optional |
| audio_url, waveform_url | https URLs (S3) |
| transcript | source segment transcript |
| mu_no | Meaning Unit number within the segment |
| meaning | the meaning that must be conveyed |
| reference_interpretation | optional model answer |
| mu_weight | optional, default 1 |

### courses.csv (one row per lesson)
`course_key, course_title, course_description, lesson_no, lesson_title, video_url, html_content, is_free`

Provide downloadable template CSVs and a sample with 1 dialogue in the admin import page.
