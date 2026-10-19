"""Downloadable CSV templates and samples for the admin import page. Sample rows are format examples only."""

DIALOGUES_HEADER = ("dialogue_key,dialogue_title,topic,difficulty,lote_language,description,instructions,segment_no,"
                    "direction,speaker_label,speaker_role,audio_url,waveform_url,transcript,mu_no,meaning,"
                    "reference_interpretation,mu_weight,is_free")

DIALOGUES_TEMPLATE = DIALOGUES_HEADER + "\n"

_B = "https://YOUR-BUCKET.s3.ap-southeast-2.amazonaws.com/ccl/sample-health-appointment"
_D = ("sample-health-appointment,SAMPLE Health clinic appointment (format example; replace),Health,Easy,fil,"
      "A receptionist and a patient arrange an appointment.,Interpret each segment into the other language.")
DIALOGUES_SAMPLE = DIALOGUES_HEADER + "\n" + "\n".join([
    f'{_D},1,EN>LOTE,Receptionist,Clinic receptionist,{_B}/seg01.mp3,{_B}/seg01.png,'
    f'"Your appointment is on Tuesday at 10:30 in the morning.",1,There is an appointment,'
    f'"Ang appointment mo ay",1,true',
    f'{_D},1,EN>LOTE,Receptionist,Clinic receptionist,{_B}/seg01.mp3,{_B}/seg01.png,'
    f'"Your appointment is on Tuesday at 10:30 in the morning.",2,On Tuesday,sa Martes,1,true',
    f'{_D},1,EN>LOTE,Receptionist,Clinic receptionist,{_B}/seg01.mp3,{_B}/seg01.png,'
    f'"Your appointment is on Tuesday at 10:30 in the morning.",3,At 10:30,alas-diyes y medya,1,true',
    f'{_D},1,EN>LOTE,Receptionist,Clinic receptionist,{_B}/seg01.mp3,{_B}/seg01.png,'
    f'"Your appointment is on Tuesday at 10:30 in the morning.",4,In the morning,ng umaga,1,true',
    f'{_D},2,LOTE>EN,Patient,Patient,{_B}/seg02.mp3,{_B}/seg02.png,'
    f'"Pwede po bang sa hapon na lang? May trabaho po ako sa umaga.",1,'
    f'Asks whether the appointment can be in the afternoon instead,Could it be in the afternoon instead?,1,true',
    f'{_D},2,LOTE>EN,Patient,Patient,{_B}/seg02.mp3,{_B}/seg02.png,'
    f'"Pwede po bang sa hapon na lang? May trabaho po ako sa umaga.",2,'
    f'Reason: works in the morning,I work in the mornings.,1,true',
]) + "\n"

COURSES_HEADER = "course_key,course_title,course_description,lesson_no,lesson_title,video_url,html_content,is_free"
COURSES_TEMPLATE = COURSES_HEADER + "\n"
COURSES_SAMPLE = COURSES_HEADER + "\n" + "\n".join([
    'intro-to-ccl,Introduction to CCL Test (format example; replace),What the CCL test is and how it is marked.,1,'
    'SAMPLE What is the CCL test?,https://www.youtube.com/embed/VIDEO_ID,"<p>Sample lesson text. Replace before '
    'launch.</p>",true',
    'intro-to-ccl,Introduction to CCL Test (format example; replace),What the CCL test is and how it is marked.,2,'
    'SAMPLE How the test is marked,,"<h2>Marking</h2><p>Sample lesson text. Replace before launch.</p>",true',
]) + "\n"
