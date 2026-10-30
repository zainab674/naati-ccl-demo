# Scoring validation

The platform shows students an "estimated score /90" and Pass/Fail. That number is only worth showing if it agrees
with what certified NAATI CCL examiners would give the same recordings. This document records how that is checked,
what has been measured, what changed because of it, and what the platform may claim.

## Status (2026-10-30)

- **No agreement has been measured yet.** No examiner-marked student recordings exist yet (requested from
  Benchmark: docs/validation/DATA_REQUEST.md). This document contains no number about the platform's accuracy.
- Because of that, **no language is validated**, and students see **practice feedback without a score**. They still
  see each error, its explanation and a suggested version, but no total, criterion deductions, per-error deductions,
  Pass/Fail, best scores or dashboard averages, and the results email has no score. Staff still see everything, labelled.
- The study is built and tested end to end: annotation set-up, evaluation harness, Rasch analysis, frozen held-out
  split, acceptance bar (proposed), per-language gate with a CI check.

## What the score claims, and what would show it is right

The claim is: "an examiner would give about this mark, and would pass or fail you as shown". The evidence that would
support it, in order of strength:

1. **Students' real NAATI CCL results.** Students the platform called Pass should pass the real test much more often
   than those it called Fail.
2. **Blind marks from several certified examiners.** The AI is good enough when it agrees with examiners about as well
   as examiners agree with each other. That agreement between examiners is the ceiling, measured on the same
   recordings.
3. **A held-out set** that nobody looked at while changing prompts, models or penalties, scored once against a bar
   agreed in advance.

Our own reading of AI output, or the client's, is not evidence. Neither is synthetic data.

## Material

| material | status |
|---|---|
| Student recordings (audio), 40+ dialogue attempts with consent | requested |
| Each recording marked independently by 2-3 certified examiners, at error level | requested; annotation guide and Label Studio set-up ready |
| Human transcripts and hand-marked timings, about 40 answers | requested |
| Students' real NAATI results | requested where students consent |
| NAATI's own published CCL information | **read directly** (below) |

### What NAATI publishes, compared with the Scoring Brief

Read on 2026-10-30 from naati.com.au/migration-assessments/ccl/, /resources/candidate-instructions-ccl/ and
/resources/language-policy-ccl/:

- **Matches the platform:** two dialogues of about 300 words, segments of up to 35 words, 45 marks each, 90 in total;
  Pass is 63 or more overall and at least 29 per dialogue. One repeat per dialogue is free. Interpreting should start
  within 5 seconds of the chime.
- **NAATI publishes no point values.** It describes a deduction method in which marks taken off depend on how much an
  error affects the overall communication. The brief's fixed -1 per Meaning Unit and -0.5 per other error are
  Benchmark's model of that, not NAATI's rule. The study measures how far that model is from examiners' marks
  ("rubric fidelity", below) separately from how well the AI finds errors.
- **Not modelled by the platform yet:**
  - Indirect speech can lose marks, and a whole dialogue in indirect speech can invalidate the test. The evaluator
    has no error type for it.
  - The language policy penalises English numerals in Gujarati, Hindi, Malayalam and Punjabi (among others). Our
    draft guidance for those languages says common English loanwords are acceptable and does not mention numerals.
  - The whole test performance should stay under 20 minutes, and long pauses can cost marks for that reason.
  - NAATI uses no "Meaning Unit" concept in what it publishes.

  Examiners can mark `indirect_speech` and `other_language` in the annotation tool, so the report will show how much
  each gap costs before anyone changes the prompt.
- **Not published:** how many examiners mark each test, or any reliability figures. A failed candidate scoring 58 or
  more can ask for a review by a separate examiner.

## Methods

Code: `backend/validation/`. Commands: see "Running the study" below.

- **Unit of analysis.** Dialogue attempts (/45) and two-dialogue tests (/90), because those are what students see.
  Error-level statistics use segment answers. Every confidence interval is a 95% percentile bootstrap (2,000 draws)
  that resamples **students**, because answers from one student are not independent.
- **Three scores per dialogue:**
  - the examiner's mark (their own /45, or 45 minus their own deductions);
  - the brief's fixed penalties applied to the errors that examiner found;
  - the AI's score.

  Comparing the first two measures the rubric. Comparing the last two measures error identification.
- **Agreement on marks:**
  - ICC(A,1): absolute agreement, single rater (a consistently harsh rater counts as disagreement);
  - quadratic weighted kappa;
  - Bland-Altman bias and limits of agreement.

  Each is computed examiner vs examiner (the ceiling) and AI vs each examiner, on the same units, and the gap between
  the two has its own interval.
- **Pass/Fail at 29 and 63:** sensitivity, specificity, **false-pass rate** (examiner-Fail tests the AI passes) and
  the share of AI passes that examiners fail, plus calibration tables (examiners' mean mark and pass rate for each
  band of AI score).
- **Error identification:** precision and recall per error type.
  - Omission and distortion must match the same Meaning Unit.
  - Other types must match by time, within 1.0 s. AI errors are placed in time by finding their quote in the
    speech-to-text word timings.
  - Each is reported next to the same statistic between examiners.
  - Types the AI cannot report (indirect speech, wrong-language words) are listed, so their cost is visible.
- **Speech-to-text:** word error rate (jiwer) against human transcripts, overall and split into mixed
  Filipino–English answers and single-language answers.
- **Timing:** speech-start error and pause precision/recall against hand-marked timings, and the share of timing
  events within 0.5 s.
- **Quotes:** the share of AI-reported errors whose quoted words appear in the transcript.
- **Many-facet Rasch** (student × rater × Meaning Unit, with the AI as one more rater):
  - It puts the AI's severity on the examiners' scale.
  - It measures each Meaning Unit's difficulty, which turns the Meaning-Unit-count problem into a number per
    dialogue (expected misses for an average student).
  - It is fitted in Python by penalised joint maximum likelihood, and exported for an independent re-fit in FACETS or
    R TAM (`tam.mml.mfr`).
- **Held-out set:**
  - The split is by student (never by segment), frozen once. split.json stores a checksum, so edits are detected.
  - Recordings added later from held-out students are refused.
  - Scoring the held-out set needs `--final --reason`, and every held-out run is appended to a ledger. A second
    held-out run is flagged in the report.
- **Run cache:** AI results are cached under a key built from the prompt version, the models, the scoring config and
  the language guidance. Any change produces a fresh run, never a mix.

### Acceptance bar (proposed, `backend/validation/bar.yaml`)

| check | requirement |
|---|---|
| AI-vs-examiner ICC on dialogue marks | at least the examiner-vs-examiner ICC minus 0.05 |
| false-pass rate at 63 | at most 5% |
| AI quotes found in the transcript | 100% |
| timing events within 0.5 s of hand-marked | 100% |
| enough data | 40+ dialogue attempts and 15+ examiner-failed tests, otherwise "not enough data", which is not a pass |

`agreed_with_benchmark: false` until Benchmark agrees in writing. A report cannot pass while it is false. The 100%
requirements are taken literally from the brief and may be relaxed only by that same agreement, recorded with who
agreed and when.

## Results

### Measured on real data

None yet.

### Checked on synthetic data (tests only, not results)

`tests/test_validation.py` checks the harness itself:

- ICC(A,1) reproduces Shrout & Fleiss's published example (0.29).
- With an AI identical to the examiners, the report gives ICC 1, bias 0 and precision 1. It still fails the bar for
  having too few units.
- With an AI planted to over-mark omissions, the report shows negative bias, an ICC below the ceiling and lost
  precision, and the Rasch model recovers a positive AI severity.

### Meaning-Unit count: model, not data

`python -m validation simulate`. Students convey each MU with the probability shown and make one other error per
segment on average; the production engine scores each simulated dialogue (20,000 runs per row):

| MUs in dialogue | MUs conveyed | adjustment (ref 40) | mean /45 | P(pass, 29+) |
|---|---|---|---|---|
| 12 × 3 = 36 | 85% | off | 33.6 | 0.95 |
| 12 × 3 = 36 | 85% | on | 33.0 | 0.91 |
| 14 × 4 = 56 | 85% | off | 29.6 | 0.60 |
| 14 × 4 = 56 | 85% | on | 32.0 | 0.87 |
| 16 × 5 = 80 | 85% | off | 25.0 | 0.16 |
| 16 × 5 = 80 | 85% | on | 31.0 | 0.81 |
| 12 × 3 = 36 | 70% | off | 28.2 | 0.44 |
| 14 × 4 = 56 | 70% | off | 21.2 | 0.02 |
| 16 × 5 = 80 | 70% | off | 13.0 | 0.00 |
| 16 × 5 = 80 | 70% | on | 25.0 | 0.09 |

Under the current rule, the same student's chance of passing one dialogue goes from 95% to 16% depending only on how
finely the dialogue was split. The adjustment narrows that to 91% to 81%. What remains comes from longer dialogues
having more segments, and so more other errors. This is a model. Whether real examiners mark this way is what the
Rasch dialogue table will show.

## What changed, and why

- **Per-language score gate** (`config/validated_languages.yaml`, `app/services/score_visibility.py`). Scores are
  shown only for languages with a passing held-out report. That is none today, so every language shows practice
  feedback. `make check` fails when a validated language's report is missing, did not pass, or was made with a
  different prompt or scoring config from the one in the repository: changing either one requires validating again.
- **Meaning-Unit-count adjustment** (`scoring.yaml` `accuracy_normalisation`, engine `dialogue_score`). When enabled,
  a dialogue's accuracy deduction is scaled by 40 ÷ its Meaning-Unit count. **Off** until Benchmark chooses between it
  and a splitting guideline, and the Rasch analysis on real marks supports the choice.
- **No change to prompts, penalties or language guidance.** Changing them without development-set data would be
  tuning blind. The NAATI gaps above (indirect speech, English numerals) are the first candidates to test on the
  development set once marks arrive.

## What failed or is limited

- Nothing has been measured, so nothing is known about the AI's accuracy. Any statement otherwise would be invented.
- The data request asks for 40 dialogue attempts rather than 150 segments: 150 segments is about 11 dialogues, and
  the interval on an ICC from 11 units is wider than the 0.05 margin being tested.
- Errors other than omission and distortion are matched by time. An AI quote that does not appear word for word in
  the speech-to-text output gets no time and is matched only by count, which is weaker.
- The Rasch fit is joint maximum likelihood. Its estimates are slightly spread out, so a published analysis should
  use the FACETS or TAM re-fit.
- "Mixed language" in the speech-to-text figures comes from the transcriber's flag, not from automatic detection.
- Pronunciation is flagged for review rather than deducted (as before). Its agreement is reported but cannot affect
  the score.

## What the platform may claim now

- Yes: "Practice feedback: errors the AI found in your interpretation, with explanations and suggested versions."
- Not yet, for any language: an estimated NAATI score, a predicted Pass or Fail, or "as marked by NAATI examiners".
- After a language passes: "Estimated score, checked against certified NAATI examiners' marking on [n] dialogues
  (agreement [ICC] where examiners agree with each other at [ICC]). Not an official NAATI result." The numbers come
  from the committed held-out report.

## Running the study

From `backend/` with the validation requirements installed (`pip install -r requirements-validation.txt`), the
dialogues imported, and real AI keys in `.env`:

```bash
python -m validation tasks fil --audio-base-url https://…   # Label Studio tasks for examiners
python -m validation import-labelstudio fil export.json --examiners examiners.csv
python -m validation freeze fil                               # once, before looking at any results
python -m validation run fil                                  # development split: iterate here
python -m validation rasch fil
python -m validation run fil --split heldout --final --reason "bar agreed on <date>; final check"
python -m validation approve fil --by "<who at Benchmark>, <date>"   # only if the held-out report passed
python -m validation check                                    # part of make check
```

Per-run reports (with transcripts) stay in the private data folder. Only the held-out report is committed, to
`docs/validation/reports/`, with aggregate numbers only.
