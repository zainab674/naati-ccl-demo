# Examiner annotation guide (CCL scoring validation)

This guide is for the certified CCL examiners who mark student recordings for the validation study, and for whoever
prepares the files. The study compares the platform's estimated scores with examiners' marking
(docs/SCORING_VALIDATION.md). Mark as you would in a real CCL test, and record each error you deduct for.

## How to mark

- Mark **independently**. Do not discuss recordings with other examiners or look at their marks, and do not look at
  the platform's AI feedback. Disagreement between examiners is data: it sets the bar the AI is held to.
- One task is one segment answer: the source segment, its Meaning Units (MUs) and the student's recording.
- For every error, select the stretch of audio where it happens and pick one label:

| label | criterion | when |
|---|---|---|
| omission | accuracy | a Meaning Unit, or an important part of it, is missing. Give the MU number. |
| distortion | accuracy | the MU was attempted but its meaning changed. Give the MU number. |
| insertion | accuracy | information that is not in the source was added |
| grammar | language | a genuine grammatical error (not acceptable spoken variation) |
| unidiomatic_usage | language | understandable but unnatural or too literal |
| register | language | clearly wrong level of formality for the situation |
| sentence_structure | language | ideas wrongly chopped apart or wrongly linked |
| pronunciation | language | mispronunciation that makes a word hard to understand or ambiguous |
| indirect_speech | language | reported speech ("she says that...") instead of first person |
| other_language | language | words in the wrong language beyond accepted usage (e.g. English numerals where NAATI's language policy penalises them) |
| pause | fluency | a pause longer than about 3 seconds while interpreting |
| start_delay | fluency | started more than about 5 seconds after the chime |
| hesitation | fluency | filler sounds or words that interrupt the flow |
| self_correction | fluency | false start, restart or correction of something already said |

- For each error, also enter **your deduction** for it: what you would actually take off in a CCL test. NAATI
  deducts "depending on how much it impacts on the overall communication", so this need not be the platform's fixed
  -1 or -0.5. These numbers let the study measure whether fixed penalties match examiner judgement.
- If an answer has no errors, tick **No errors in this answer**. An answer with no marks and no tick counts as not
  reviewed.
- Optionally type the student's words for the error (quote).
- At the end of each dialogue, give the dialogue mark out of 45 you would award (dialogue_marks.csv). If you do not,
  45 minus your deductions is used.

## Files (prepared by Benchmark or the platform team)

All files go in `VALIDATION_DATA_DIR/<language>/` (default `backend/data/validation/fil/`). That folder is outside
version control: it holds student audio and marks, which are personal data. Use pseudonymous ids (S001, E1), never
names or emails.

| file | columns | notes |
|---|---|---|
| recordings.csv | recording_id, student_id, test_id, dialogue_key, segment_no, audio_path, consent | one row per segment answer; test_id groups the two dialogues of one sitting; consent must be `yes` or the row is excluded |
| annotations.csv | recording_id, examiner_id, kind, error_type, mu_no, start_s, end_s, deduction, quote | written by `python -m validation import-labelstudio`, or by hand in the same format; kind `none` = reviewed, no errors |
| dialogue_marks.csv | test_id, dialogue_key, examiner_id, score | optional; the examiner's own /45 |
| transcripts.csv | recording_id, transcript, mixed_language | optional; a human transcript of the student's answer, `mixed_language` yes when it mixes Filipino and English |
| timings.csv | recording_id, speech_start_s, pauses | optional; hand-marked in Praat or ELAN: seconds from the chime to the first word, and pauses over 3 s as `start-end;start-end` |
| exam_results.csv | student_id, exam_date, total, dialogue_1, dialogue_2, result | optional; the student's real NAATI CCL result, with their consent |

The dialogues used must be imported into the platform first (their Meaning Units are what everyone marks against).

## Label Studio set-up

1. Create a project and paste `backend/validation/label_studio_config.xml` as its labeling config.
2. `python -m validation tasks fil --audio-base-url <where the audio files are served>` writes
   `label_studio_tasks.json`; import it into the project.
3. Give each examiner their own Label Studio account, and set the project to show every task to 2 or 3 annotators
   (Settings > Annotation > Overlap).
4. When marking is done, export as JSON and run
   `python -m validation import-labelstudio fil export.json --examiners examiners.csv`
   where examiners.csv maps each Label Studio account to a pseudonym (`label_studio_user,examiner_id`).

ELAN or Praat can be used instead for the timing files; Label Studio is only needed for the error marks.
