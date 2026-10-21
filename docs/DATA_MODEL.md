# Data model (client's structure, adapt names to SQLAlchemy conventions)

Use UUID primary keys, `created_at`/`updated_at` on everything, Alembic migrations.

1. **User**: id, first_name, last_name, email (unique), password_hash, role (student/admin), preferred_language_id?,
   target_exam_date?, subscription_status (Active/Trial/Expired/Inactive), stripe_customer_id, last_login_at.
2. **Language**: id, name, code, native_name, language_type (English/LOTE), status, supports_speech_to_text,
   supports_text_to_speech. English exists as a record but is the fixed test language.
3. **LanguagePair**: id, english_language_id, lote_language_id, display_name ("English <-> Filipino"), status.
   Validation: english id must be the English record; lote must be LOTE; no EN-EN; no duplicates.
4. **Topic**: id, name, description, status, sort_order.
5. **Dialogue**: id, key (slug, for CSV idempotency), title, topic_id, language_pair_id, description, difficulty
   (Easy/Intermediate/Difficult), instructions, status (Draft/Published/Archived), maximum_score (45 per dialogue,
   attempt total 90), passing_score, estimated_duration, sort_order, version, is_free, created_by.
6. **Segment**: id, dialogue_id, segment_number, source_language_id, target_language_id (must be the pair's EN/LOTE and
   differ), audio_file (stored key + HLS package ref), source_audio_url (imported), transcript, speaker_label,
   speaker_role, duration_seconds, word_count, waveform_image, active.
7. **MeaningUnit**: id, segment_id, meaning_unit_number, meaning, reference_interpretation, reference_language_id,
   weight (default 1), active.
8. **DialogueAttempt**: id, user_id, dialogue_id, language_pair_id, status (In Progress/Completed/Abandoned),
   current_segment_number, maximum_score, passing_score, accuracy_completeness_deduction, language_quality_deduction,
   fluency_deduction, total_deductions, total_score, total_repeats, result (Pass/Fail), scoring_status
   (Pending/Processing/Completed/Failed), attempt_number, dialogue_version, overall_feedback, started_at,
   submitted_at, finished_at.
   (A mock test of 2 dialogues = a MockTestAttempt grouping 2 DialogueAttempts; total out of 90, per-dialogue min.)
9. **SegmentAttempt**: id, dialogue_attempt_id, segment_id, source/target language ids, audio_user, transcript_user,
   stt_words (JSON timestamps), play_count, record_count, the three deductions, total_deduction, ai_feedback,
   scoring_status, scoring_confidence, reviewed_by_admin, submitted_at, skipped (bool).
10. **AccuracyCompletenessEvaluation**: id, segment_attempt_id, evaluation_type (MeaningUnit/Insertion),
    meaning_unit_id?, result (Correct/Omission/Distortion/Insertion), source_meaning, student_meaning, explanation,
    deduction (0 or 1, set by platform), confidence.
11. **LanguageQualityError**: id, segment_attempt_id, language_id, error_type (Grammar/UnidiomaticUsage/Pronunciation/
    Register/SentenceStructure), student_text, suggested_version, explanation, timestamp_seconds, deduction (0.5,
    0 for review-only pronunciation), detection_method (AI/AudioAnalysis/Manual), confidence, needs_review.
12. **FluencyError**: id, segment_attempt_id, language_id, error_type (Pause/StartDelay/Hesitation/SelfCorrection),
    timestamp_seconds, duration_seconds, transcript_excerpt, explanation, deduction (0.5), detection_method, confidence.
13. **RepeatEvent**: id, dialogue_attempt_id, segment_attempt_id, repeat_number, created_at.
14. **AIScoringRun**: id, segment_attempt_id, source/target language ids, provider, model, prompt_version,
    request_data (JSON), raw_response (JSON), processed_result (JSON), status (Pending/Success/Failed), error_message,
    created_at, completed_at.
15. **LanguageScoringConfig**: id, language_id, grammar_guidelines, register_guidelines, hesitation_markers (JSON),
    pronunciation_config (JSON), ai_prompt_addition, version, active. Seed one for Filipino.
16. **AdminReview**: id, segment_attempt_id, reviewed_by, original_deduction, revised_deduction, review_notes,
    status (Pending/Reviewed/Approved).

Additional MVP tables:
- **Course**: id, key, title, description, status, sort_order, is_free, language_pair_id? (null = all languages).
  **CourseChapter**: id, course_id, number (unique per course), title. Lesson.chapter_id? (null = listed after the chapters). **Lesson**: id, course_id, lesson_number, title,
  video_url, html_content (sanitised), is_free, status. **LessonProgress**: user_id, lesson_id, completed_at.
- **Plan**: id, name (Self-Study / Coaching), stripe_price_id, price_display, features (JSON), active.
- **Subscription/Payment**: user_id, stripe ids, status, current_period_end, amount, currency, receipt_url.
  Subscription.source = stripe | manual; a manual (teacher) grant also stores granted_by_id and a note.
  User.access_expires_at ends a manual grant automatically; User.enrolled_by_id marks teacher-created accounts.
- **SiteContent**: key/value JSON for home page, FAQ, reviews, landing copy (admin-editable later).
- **ImportJob**: id, type (dialogues/courses), file name, status, dry_run report (JSON), counts, created_by.
- **EmailLog**: to, template, status, provider_id, error.
- **PlatformSetting**: key ("theme" | "email"), value (JSON), updated_by. Email secrets are stored encrypted (Fernet,
  key derived from SECRET_KEY).
- **Resource** (learning hub): key, title, description, resource_type (Ebook/Glossary/Worksheet/Audio/Video/Article/
  Link), language_pair_id? (null = all), topic_id?, status, is_free, sort_order, private file (file_key, file_name,
  file_size, content_type) or external_url or html_content (sanitised).
- Keep from the demo: PlayGrant / protected media, SecurityEvent, StoredFile (if useful).

Relationships: Language -> LanguagePair -> Dialogue -> Segment -> MeaningUnit; Topic -> Dialogue;
User -> DialogueAttempt -> SegmentAttempt -> {AccuracyCompletenessEvaluation, LanguageQualityError, FluencyError,
AIScoringRun, AdminReview}; DialogueAttempt -> RepeatEvent. Each Segment states its direction (EN->LOTE or LOTE->EN),
so any new LOTE is just a new Language + LanguagePair with no schema change.
