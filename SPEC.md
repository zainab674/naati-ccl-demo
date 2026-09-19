# NAATI CCL Prep Platform: Demo Build Spec

**Client:** Benchmark Education Solutions (Nipun Jain)
**Status:** Unpaid proof-of-concept. Bounded to the scope below.
**Target build time:** 3 days
**Prepared:** 19 Sep 2026
**Supersedes:** oet-lms-demo-spec.md

---

## 1. What this demo has to prove

Nipun asked for an LMS with practice tests, AI marking, practice questions, video tutorials and an online session calendar, and pointed at NaCl Prep (naclprep.com) as the reference for NAATI CCL. He runs a content-producing organisation and already knows what a working prep business looks like. He is deciding whether one developer can build the hard parts.

The demo proves three things:

1. **A realistic CCL exam player.** Segment-by-segment dialogue audio, the student records their interpretation after each chime, repeats are counted, and the flow feels like the real test.
2. **AI marking of spoken interpretation that he can trust and tune.** Speech to text, then marking against a structured rubric, with per-segment feedback that quotes what the student actually said. The rubric and deductions live in config so his own marking logic drops in.
3. **A product shape at least as good as NaCl Prep.** A tagged dialogue library, mock tests, progress tracking and the retention features that make that product sell, plus the modules on his list (videos, sessions) visible in the navigation.

Content protection is a supporting feature, not a headline. He already said a determined user can record from the soundcard, so we show the sensible baseline and explain that watermarking is the real answer to that (section 7).

**Judgement rule:** if a feature does not serve one of those three points, it is a stub or it is cut.

---

## 2. Assumptions (not confirmed with the client)

We are not sending him a list of questions before the demo. Instead, we build on these defaults and design each one so it is cheap to change. The demo call is where he corrects them.

| Assumption | Default | Why it is safe |
|---|---|---|
| Exam | NAATI CCL | He sent us to NAATI research. The core engine is exam-agnostic (section 9) and OET can be added as a different activity type. |
| Language pair | Hindi to and from English | Largest CCL language group. The language pair is a field on each dialogue, so adding more is a data change. |
| Marking logic | Placeholder rubric based on public NAATI CCL criteria | He said he will share his logic. Rubric, deductions and pass rules are all in config. |
| AI provider | One provider behind `transcribe()` and `mark_interpretation()` | He wants to decide later between static code and APIs. Marking is split so the rule-based parts (repeats, timing, pass or fail) are already static code and only the language judgement uses a model. |
| Content | Our own synthetic dialogues | He said "we develop our own content" and does not copy anyone else's. |

On the demo call, one line covers all of these: "Everything he might want different (exam, language, rubric, provider) is config, and here is where it lives."

---

## 3. Scope

### In scope

- Student login (seeded accounts, no signup flow)
- Student dashboard in the style of NaCl Prep: exam-date countdown, practice counter, mock-test progress, latest dialogues
- **Dialogue library:** a list filtered by domain, difficulty and language, with a report-issue action on each item
- **Practice mode:** one dialogue, segment by segment, record, instant AI feedback
- **Mock test mode:** two dialogues under exam conditions, marked out of 90 with a pass or fail result
- Results page with per-segment transcript, deductions and feedback
- Attempt history
- Minimal admin: view attempts, listen to the student's recording, see AI output, override a score
- Content ops panel: add a dialogue by pasting a script, then TTS generation and segmentation (shows how he scales his library)
- Protected audio delivery (segmented, signed, rate-limited)

### Stubbed (visible, disabled, with a "coming soon" badge)

Video tutorials, book a live session (calendar), practice questions bank, other language pairs, request a new dialogue, a Telegram or community link.

A stub gets a real page with a short description of what it will do. A dead link is not acceptable.

### Out of scope

Payments, signup and email verification, mobile apps, real NAATI or Benchmark content, production auth hardening, multi-tenancy, watermarking implementation.

---

## 4. The NAATI CCL format (what the player models)

The values below are based on public NAATI CCL information. **Every number is a config value**, so if his logic or NAATI's current rules differ, we change the config and not the code.

- A test has **2 dialogues**, each on a different domain (health, legal, financial, education, community, business, consumer affairs, immigration, and so on).
- Each dialogue runs between an English speaker and a LOTE (language other than English) speaker, and is split into **segments** of up to about 35 words.
- After each segment there is a **chime**, and the candidate interprets into the other language.
- Candidates may **request a repeat** of a segment. Repeats beyond the allowance incur a deduction.
- Each dialogue is **marked out of 45**, for a **total of 90**. The pass mark is **63 overall, with a minimum of 29 in each dialogue**.
- Marking is **deduction-based**: points are lost for accuracy (distortions, omissions, insertions), language quality, register, and delivery (long pauses, hesitation, self-correction).

```yaml
# config/ccl.yaml
dialogue_max: 45
total_max: 90
pass_total: 63
pass_min_per_dialogue: 29
repeats:
  free_per_dialogue: 1        # placeholder, to be confirmed
  deduction_per_extra: 1
response_window_seconds: 30   # max recording length per segment
chime_asset: chime.mp3
```

---

## 5. Users and roles

| Role | Seeded accounts | Can do |
|---|---|---|
| Student | 2 | Practice, take the mock test, view own results and history |
| Assessor/Admin | 1 | View all attempts, play recordings, see AI reasoning, override, add dialogues |

Seed with a script. There is no roles UI.

---

## 6. Screens and flows

### 6.1 Login
Email and password. Redirect by role.

### 6.2 Student dashboard (mirrors the NaCl Prep layout he already knows works)
- Exam-date card: "Not set, tap to set", then a days-remaining countdown
- Total practiced counter
- Mock-test card with progress (for example 58/90 from last attempt) and "Start mock test"
- Stub cards for Video Lessons, Live Coaching / Book a Session, Practice Questions and Community
- "Latest dialogues" table: number, title, scenario line, difficulty, domain tag, report issue
- Recent attempts linking to results

### 6.3 Dialogue library
- Filter by domain, difficulty and language pair, plus a search box
- Each row opens the dialogue in Practice mode
- "Report issue" opens a small form that is stored and shown in admin

### 6.4 Dialogue player, the critical screen

This is what his students spend their time in, and he will judge the product on it.

Flow for each segment:
1. The segment audio plays. A speaker label (English or Hindi) is shown with a speaking indicator.
2. The chime plays, and **recording starts automatically** with a visible level meter and countdown (`response_window_seconds`).
3. The student taps **Done** (or the window runs out). The recording uploads in the background and the next segment starts.
4. The **Repeat** button replays the current segment once before recording. It is counted, and the remaining allowance is shown.

Requirements:
- **No seek bar and no scrubbing.** Progress is shown as "Segment 7 of 12".
- **Server-enforced state.** The server records which segment was issued, how many repeats were used and which segments were recorded. A refresh resumes at the current segment. It does not restart the dialogue or reset the repeat count.
- **Mic check** before starting: record 3 seconds and play it back. If mic permission is denied, the student gets a clear message and not a broken screen.
- **Practice mode:** feedback for a segment can be shown immediately (a toggle), and the student can retry a segment.
- **Mock mode:** no feedback until the end, no retries, and both dialogues run back to back.
- Tab blur is logged and shown to the assessor.
- Each segment is uploaded as it is recorded, so a crash at segment 11 does not lose segments 1 to 10.

### 6.5 Results page
- Headline: **score out of 90** (mock) or out of 45 (single dialogue), with a clear PASS or FAIL against both rules
- Per dialogue: score and a breakdown of deductions by category
- Per segment, collapsible:
  - Source text
  - What the student said (the transcript), with playback of their recording
  - Reference interpretation
  - Deductions, each with a short explanation that **quotes the student's words**
- "Marked by AI" or "Reviewed by assessor" state
- If an assessor overrode a score, show the original, the override and the note

### 6.6 Assessor view
- Attempts table: student, dialogue or mock, date, AI score, status, tab-blur count
- Open an attempt: segment by segment, with their audio, the transcript, the AI deductions and the raw model reasoning
- Override a segment's deductions or the dialogue score, add a note and save. The student's results page updates.
- Report-issue inbox

### 6.7 Content ops panel (small, but it matters to him)
- Paste a dialogue script as alternating speaker lines, with a title, domain, difficulty and a reference interpretation for each segment
- Click "Generate". The backend runs TTS for each segment with two voices, adds the chime, segments to HLS and publishes to the library.
- This shows him that his team can produce dialogues at NaCl Prep's pace (they have about 320) without a developer.

---

## 7. AI marking

### 7.1 Pipeline

```
student recording (per segment, webm/opus)
  → transcribe(audio, language)        # STT, returns text + word timestamps
  → delivery_metrics(timestamps)       # static code: long pauses, fillers, restarts
  → mark_interpretation(source, reference, transcript, rubric)   # model call
  → apply_deductions(config)           # static code: repeats, totals, pass/fail
```

Only `mark_interpretation` needs a language model, and only `transcribe` needs a speech model. Repeats, timing, totals and pass or fail are deterministic code. This is the split to point out when he raises "static code vs APIs".

### 7.2 Rubric (placeholder, to be replaced by his logic)

```yaml
# config/rubric.yaml
categories:
  - id: accuracy
    name: Accuracy
    checks: [distortion, omission, insertion]
  - id: language_quality
    name: Language quality
    checks: [grammar, word_choice, idiom]
  - id: register
    name: Register
    checks: [formality_mismatch]
  - id: delivery
    name: Delivery
    checks: [long_pause, hesitation, self_correction, incomplete]
severity_points: { minor: 0.5, major: 1, critical: 2 }
```

### 7.3 Model contract
- One call per segment (batched per dialogue for speed), with the source segment, the reference interpretation, the student transcript, delivery metrics and the rubric as input
- **Structured JSON output**: a list of issues, each with `category`, `check`, `severity`, `quote` (an exact substring of the student transcript) and `explanation`
- Validate against a schema, check that every `quote` really appears in the transcript, retry once, and **fail visibly** if it still does not validate
- Store the raw response for the assessor
- The model never outputs a score. Points come from `severity_points`, which keeps scores consistent, auditable and tunable by him.

### 7.4 Speech-to-text reality check
STT on accented or code-mixed Hindi and English will make mistakes, and a transcription error could be mistaken for an interpretation error. So:
- Always show the student what was heard, next to their own recording
- Flag low-confidence transcripts ("Audio unclear, reviewed by assessor") instead of marking them silently
- Raise this in the demo before he asks. It shows we know where AI marking fails.

---

## 8. Content protection (supporting, not the headline)

Build the baseline and explain it in one admin panel:

- Dialogue audio served as **segmented HLS**, never as a single downloadable file
- **Signed URLs that expire in 5 minutes**, issued per attempt and bound to the session
- Dialogue text and reference interpretations are **never sent to the client during an attempt**. Only the results page shows them, and only after submission.
- **Rate limiting and an anomaly flag**: a student practises a few dialogues an hour, while a scraper pulls dozens. Flag the account.
- A protection status panel so he can see this for himself

**On his soundcard point:** he is right that anything played can be recorded. The answer is to make leaks traceable, not to prevent them. That means **per-user audio watermarking**: an inaudible mark embedded per account, so a copied recording can be traced to the account it came from. Given what he just paid to document with OET Ultimacy, that is the feature that changes the outcome. **Explain it and do not build it for the demo.** Say that plainly.

---

## 9. Data model (exam-agnostic core)

`activities.type` is `ccl_dialogue` for now. OET Listening or Writing would be new types on the same tables. That is one sentence in the demo and it covers the chance that he also wants OET.

```
users              id, email, password_hash, role, name, exam_date
activities         id, type, title, scenario, domain, difficulty,
                   language_pair, config_json, published
segments           id, activity_id, order, speaker, language,
                   source_text, reference_text, asset_key
mock_tests         id, title, activity_ids[]
attempts           id, user_id, activity_id|mock_test_id, mode(practice|mock),
                   started_at, submitted_at, status, current_segment,
                   repeats_used_json, integrity_events_json
segment_responses  id, attempt_id, segment_id, audio_key, transcript,
                   stt_confidence, delivery_metrics_json, retries
markings           id, segment_response_id, source(ai|assessor), issues_json,
                   points_deducted, raw_model_json, note, created_at
scores             id, attempt_id, activity_id, score, max, passed,
                   overridden_by, computed_at
issue_reports      id, user_id, activity_id, text, status
```

## 10. API

```
POST  /auth/login
GET   /me                                  PATCH /me (exam_date)
GET   /activities?domain=&difficulty=&lang=
POST  /attempts                            start (practice|mock), returns attempt + token
GET   /attempts/:id/segments/current       next segment meta + signed m3u8 URL
POST  /attempts/:id/segments/:sid/repeat   server counts it
POST  /attempts/:id/segments/:sid/audio    upload recording
POST  /attempts/:id/submit                 triggers marking
GET   /attempts/:id/results
POST  /activities/:id/report
GET   /admin/attempts                      assessor
POST  /admin/markings/:id/override         assessor
POST  /admin/activities                    content ops: script → TTS → HLS
```

## 11. Stack

- **Frontend:** Next.js (App Router), TypeScript, Tailwind. MediaRecorder for capture and hls.js for playback.
- **Backend:** FastAPI (Python). All marking logic lives here.
- **DB:** Postgres
- **Media:** S3-compatible storage. ffmpeg for HLS segmentation and chime insertion.
- **STT:** a Whisper-class model with Hindi support, behind `transcribe()`
- **LLM:** Claude by default, behind `mark_interpretation()`
- **TTS:** a licensed provider with natural Hindi and English voices (two distinct voices per dialogue)
- **Deploy:** one public URL. No local-only demo.

## 12. Seed content (write ourselves, never source)

- **6 dialogues**, Hindi and English, each 8 to 12 segments (demo length; real CCL dialogues are longer). Cover domains such as Health, Legal, Financial, Education, Community and Consumer Affairs, with mixed difficulty. Each segment needs source text and a reference interpretation.
- **1 mock test** made of 2 of those dialogues
- Generate all audio through the content ops pipeline. That proves the pipeline too.
- **Student A** has a completed mock (for example 58/90, FAIL, with 24 in dialogue 2) plus several practice attempts, so the dashboard, history and pass-rule logic all have something to show on first load
- **Student B** is fresh, to show the first-run experience
- One report-issue entry in the admin inbox

Every screen he opens must have something in it.

## 13. Acceptance criteria

The demo is done when a person who has never seen it can, unaided:

1. Log in as Student A and see a populated dashboard with a countdown, counters, mock progress and the latest dialogues
2. Filter the library and open a dialogue in practice mode
3. Pass the mic check, interpret segments, use one repeat and see the allowance go down, then refresh mid-dialogue and resume at the same segment with the repeat still counted
4. See per-segment feedback with their own words quoted and their recording playable
5. Take the mock test and get a score out of 90 with PASS or FAIL, correctly applying the 29-per-dialogue rule
6. Log in as the assessor, open that attempt, listen to a segment, read the AI reasoning, override it, and see the student's result change
7. Paste a new dialogue script into content ops and see it appear in the library, playable
8. Open devtools, try to grab a dialogue audio file, and fail

Points 3 and 7 are the ones to rehearse. Point 3 shows the player holds up under exam conditions. Point 7 shows how his team scales the library.

## 14. Suggested split, 3 days

| Day | Work |
|---|---|
| 1 | Schema, auth, seed script, content pipeline (script → TTS → chime → HLS), signed segment delivery. Write the 6 dialogues. |
| 2 | Dialogue player: segment flow, recording, repeats, server state and resume, uploads, mock mode. Dashboard and library. |
| 3 | STT and marking pipeline with schema validation, results page, assessor view and override, content ops UI, stubs, deploy, rehearse. |

Build the player first. Mic permissions, autoplay rules (the start needs a user gesture), recording on Safari, and resuming after a refresh are where the time goes.

## 15. Things to raise on the demo call, without being asked

These go into the demo walkthrough. They are not a pre-build questionnaire.

- "The rubric, deductions and pass rules are config. Send me your marking logic and it goes straight in."
- "Only the language judgement uses AI. Repeats, timing and totals are plain code, which covers your static-code-or-API question."
- "Hindi is the demo pair. More languages are a data change."
- "Same engine, different activity type. OET Listening or Writing sits on the same tables."
- "Where AI marking can go wrong: transcription on accented speech. That's why the student sees what was heard and unclear audio goes to a human."
- "Watermarking is how you would trace a leak like the one we just documented."

---

## 16. What this demo is not

It is not an MVP and not production code, and it should not be presented as either. Auth is thin, there is no billing and no real content, and dialogues are demo length. It is a vertical slice that answers one question: can this developer build the hard parts of a NaCl Prep-class platform for Benchmark.
