# AI Scoring Brief (from the client, Benchmark Education)

Purpose: an **estimated** CCL performance score from the student's recorded interpretation of each segment.
Three criteria, scored independently: **Accuracy & Completeness**, **Language Quality**, **Fluency**.

> The AI identifies and classifies errors. The platform applies predefined numerical penalties.
> We do not prompt the AI to "give a score out of 90". The system must be structured and auditable,
> so a scoring rule can change without changing the AI prompt.

## 1. Accuracy & Completeness: -1 per affected Meaning Unit
Before assessing, the source segment is broken into **Meaning Units (MUs)**: distinct pieces of information that must be
communicated accurately. Example: "Your appointment is on Tuesday at 10:30 in the morning." ->
MU1 there is an appointment; MU2 on Tuesday; MU3 at 10:30; MU4 in the morning.

Error types:
- **Omission**: an MU (or an important part) is missing. Source "...Tuesday at 10:30 in the morning", student
  "Ang appointment mo ay sa Martes." -> 10:30 and morning omitted.
- **Insertion**: information not in the source is added. Source "on Tuesday", student "sa Martes ng umaga" (added "morning").
- **Distortion**: the MU is attempted but its meaning changes. "10:30" -> "alas-diyes" (10:00).

For each error the AI returns: which MU, error type, short explanation. Example:
```json
{"meaning_unit":"MU3","source_meaning":"Appointment is at 10:30","student_meaning":"Appointment is at 10:00","error_type":"distortion","deduction":1}
```
**Assess meaning, not word-for-word translation.** Many valid renderings exist ("Kailangan mong isumite ang aplikasyon
bago mag-Biyernes", "Dapat ma-submit mo ang application bago Friday", ...). Ask "was the MU transferred accurately?",
never "were the same words used as the reference?".

## 2. Language Quality: -0.5 per occurrence
Not MU-based. Types:
- **Grammar**: tense, agreement, articles, prepositions, word forms, grammatical markers. Only genuine errors, not
  acceptable spoken variation.
- **Unidiomatic usage**: understandable but unnatural: unnatural combinations, overly literal translation, wrong
  collocations, awkward expressions, wrong context. (If meaning is intact this is Language Quality, not Accuracy.)
- **Pronunciation**: mispronunciation that affects quality/understanding or creates ambiguity. Ideally judged from
  audio, not transcript. **MVP: flag for admin review, do not auto-deduct (config switch).**
- **Register**: formal / neutral-professional / casual must match the situation; significant mismatch = -0.5.
- **Sentence structure**: accidental *sentence chopping* (ideas that belong together broken into fragments) and
  accidental *sentence linking* (separate ideas wrongly combined so the relationship is confused).

## 3. Fluency: -0.5 per occurrence
Mostly from audio and timing, not the transcript.
- **Pause during interpretation > 3 s**: -0.5. Normal short pauses are not penalised.
- **Delay before starting > 5 s** after recording starts: -0.5. Detect programmatically, not by the LLM.
- **Hesitation**: repeated fillers that interrupt flow ("ah", "uh", "umm", "ahh", repeated filler words). Distinguish
  natural speech from genuine hesitation.
- **Self-correction**: false starts, restarting a phrase, rewinding, correcting what was said
  ("The appointment is on Monday, sorry, Tuesday at ten").

## Summary table
| Criterion | Error type | Penalty |
|---|---|---|
| Accuracy & Completeness | Omission / Insertion / Distortion | -1 per affected MU |
| Language Quality | Grammar / Unidiomatic / Pronunciation / Register / Sentence structure | -0.5 per occurrence |
| Fluency | Pause > 3 s / Delay > 5 s / Hesitation / Self-correction | -0.5 per occurrence |

## Architecture (split responsibilities)
**AI identifies:** MUs in the source (suggestion only, admin-approved MUs are authoritative), whether each MU was
transferred, omissions, insertions, distortions, grammar, unidiomatic usage, register, sentence structure, and
self-corrections/hesitations where reliably detectable.

**Audio/programmatic analysis identifies:** start-of-speech timestamp, pauses > 3 s, delay > 5 s, potential hesitation
events, audio info for pronunciation review.

**Platform calculates:** Accuracy deduction = affected MUs x 1; Language deduction = errors x 0.5;
Fluency deduction = errors x 0.5. Segment score + detailed feedback.

## Segment pipeline
Source audio + transcript -> Meaning Units -> student listens -> student records -> STT + audio timing analysis ->
AI compares source MUs vs interpretation -> AI returns accuracy, language and fluency-language events ->
platform adds programmatic timing events -> platform applies deductions -> segment score + feedback.

Structured output shape:
```json
{
  "accuracy_completeness": [{"meaning_unit":"MU3","source_meaning":"...","student_interpretation":"...","error":"distortion","explanation":"..."}],
  "language_quality": [{"error":"unidiomatic_usage","student_text":"...","suggested_version":"...","explanation":"..."}],
  "fluency": [{"error":"self_correction","transcript_excerpt":"...","explanation":"..."}]
}
```
(Deduction values in the stored records are filled by the platform from config, not trusted from the model.)

**Key principle:** Meaning Units are the foundation of Accuracy & Completeness. Language Quality and Fluency are
occurrence-based. The three criteria are scored independently so the framework can explain exactly why points were
deducted.

## Score totals
Each dialogue max 45, total max 90. Pass: >= 63 total and >= 29 in each dialogue (values stored per Dialogue, default
from config). Floor scores at 0.
