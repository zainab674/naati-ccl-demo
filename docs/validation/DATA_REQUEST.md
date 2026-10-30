# What we need from Benchmark to validate the scoring

The platform shows students an estimated CCL score and Pass/Fail. Before students see those numbers, we need to show
that they agree with how certified NAATI CCL examiners mark. Until then, students get practice feedback (the errors
found, explanations and suggested versions) without a score. This is what the check needs, for Filipino first.

1. **Student recordings, with consent.** At least **40 complete dialogue attempts**, about 560 segment answers. That
   is 20 or more students each doing a two-dialogue practice test, including strong, borderline and weak students.
   Audio files, not transcripts. Each student agrees in writing that their recordings may be used to check the
   scoring. We use pseudonymous ids only.
   *Why 40, not 150 segments:* the score that matters is per dialogue. 150 segments are only about 11 dialogues, too
   few to tell good agreement from bad (the uncertainty would be wider than the difference we are testing).
2. **Two or three certified CCL examiners per recording**, marking independently in Label Studio (we set it up; see
   ANNOTATION_GUIDE.md). For each error: the Meaning Unit, the error type, where it is in the audio, and their own
   deduction. A dialogue mark out of 45 at the end of each dialogue. About 15 to 25 hours of examiner time each.
3. **Human transcripts and hand-marked timings** for about 40 of the answers (when speech starts, and pauses over 3 s).
   A bilingual assistant can do this in Praat or ELAN.
4. **Real NAATI CCL results**, where students agree to share them: date, total, the two dialogue marks, Pass/Fail.
5. **Agreement on the pass bar before the final check** (in backend/validation/bar.yaml):
   - the AI agrees with examiners on dialogue marks nearly as well as examiners agree with each other (within 0.05
     intraclass correlation);
   - at most **5%** of tests that examiners fail are called Pass by the platform (a student told "Pass" who would fail
     books the real exam too early);
   - every error the AI reports quotes words that are really in the answer, and its timings are within 0.5 s.
6. **Two scoring questions** the check will inform, and Benchmark should decide:
   - Fluency penalties: the Scoring Brief says -0.5, the MVP scope page says -0.2.
   - Meaning Units: with -1 per Meaning Unit, how finely a dialogue is split changes how hard it is to pass. Either
     agree a splitting guideline (about how many MUs per 300-word dialogue) or switch on the built-in adjustment that
     gives every dialogue the same accuracy budget.
