"""DEMO content for development and client walkthroughs (loaded by `python -m app.demo_data`, never in production).

Everything here is marked DEMO. The dialogue translations were written for the demo and have NOT been checked by a
NAATI-credentialed translator; the audio is synthetic (speech-like tones, not real speech). Replace with Benchmark's
own content before any real use.

Segment tuple: (direction, speaker_role, transcript, [meaning units]). A meaning unit is (meaning, reference
rendering) or (meaning, reference rendering, distorted rendering) — the distorted version is what a demo student
says when the demo marks that unit as a distortion.
"""

EN, LOTE = "EN>LOTE", "LOTE>EN"

DIALOGUES = [
    {
        "key": "demo-fil-medical-appointment", "lote": "fil", "title": "DEMO Medical appointment", "topic": "Health",
        "difficulty": "Easy", "is_free": True,
        "description": "A patient rebooks an appointment with the clinic receptionist.",
        "segments": [
            (EN, "Receptionist", "Good morning. Your appointment with Dr Santos is on Tuesday at 10:30 in the morning.", [
                ("Appointment with Dr Santos", "may appointment po kayo kay Dr Santos"),
                ("On Tuesday", "sa Martes"),
                ("At 10:30 in the morning", "nang alas-diyes y medya ng umaga", "nang alas-onse ng umaga")]),
            (LOTE, "Patient", "Pwede po bang sa hapon na lang? May trabaho po ako sa umaga.", [
                ("Asks for an afternoon time instead", "could it be in the afternoon instead"),
                ("Works in the morning", "i work in the mornings")]),
            (EN, "Receptionist", "We have a free slot at 3 pm on Thursday. Please bring your Medicare card.", [
                ("Free slot at 3 pm on Thursday", "may bakanteng oras po sa alas-tres ng hapon sa Huwebes"),
                ("Bring your Medicare card", "pakidala po ang inyong Medicare card")]),
            (LOTE, "Patient", "Sige po, Huwebes ng alas-tres. Salamat po.", [
                ("Accepts Thursday at three", "okay thursday at three"),
                ("Thanks", "thank you")]),
        ],
    },
    {
        "key": "demo-fil-rental-bond", "lote": "fil", "title": "DEMO Rental bond dispute", "topic": "Housing",
        "difficulty": "Intermediate", "is_free": False,
        "description": "A tenancy officer explains a landlord's claim on a tenant's bond.",
        "segments": [
            (EN, "Tenancy officer", "Your landlord wants to keep 400 dollars from your bond for cleaning.", [
                ("Landlord wants to keep $400 from the bond", "gusto po ng landlord ninyo na kunin ang 400 dolyar mula sa inyong bond",
                 "gusto po ng landlord ninyo na kunin ang 40 dolyar mula sa inyong bond"),
                ("For cleaning", "para sa paglilinis")]),
            (LOTE, "Tenant", "Nilinis ko po ang buong bahay bago ako umalis. May mga litrato po ako.", [
                ("Cleaned the whole house before leaving", "i cleaned the whole house before i left"),
                ("Has photos", "i have photos")]),
            (EN, "Tenancy officer", "Please send the photos to us by Friday so we can review your case.", [
                ("Send the photos by Friday", "pakipadala po ang mga litrato sa amin bago mag-Biyernes"),
                ("So the case can be reviewed", "para masuri namin ang inyong kaso")]),
            (LOTE, "Tenant", "Ipapadala ko po bukas ng umaga.", [
                ("Will send them tomorrow morning", "i will send them tomorrow morning")]),
        ],
    },
    {
        "key": "demo-hi-pharmacy", "lote": "hi", "title": "DEMO Pharmacy advice", "topic": "Health",
        "difficulty": "Easy", "is_free": True,
        "description": "A pharmacist explains how to take a new medicine.",
        "segments": [
            (EN, "Pharmacist", "Take one tablet twice a day after meals for seven days.", [
                ("One tablet twice a day", "दिन में दो बार एक गोली लीजिए", "दिन में एक बार एक गोली लीजिए"),
                ("After meals", "खाने के बाद"),
                ("For seven days", "सात दिनों तक")]),
            (LOTE, "Patient", "क्या मैं यह दवा अपनी ब्लड प्रेशर की दवा के साथ ले सकता हूँ?", [
                ("Can it be taken with blood pressure medicine", "can i take this medicine with my blood pressure medication")]),
            (EN, "Pharmacist", "Yes, but do not drink alcohol while you are taking it.", [
                ("Yes, they can be taken together", "हाँ, ले सकते हैं"),
                ("No alcohol while taking it", "लेकिन इसे लेते समय शराब मत पीजिए")]),
            (LOTE, "Patient", "ठीक है, धन्यवाद। अगर मुझे चक्कर आए तो क्या करूँ?", [
                ("Okay, thanks", "okay thank you"),
                ("What to do if dizzy", "what should i do if i feel dizzy")]),
        ],
    },
    {
        "key": "demo-hi-job-centre", "lote": "hi", "title": "DEMO Job centre", "topic": "Employment",
        "difficulty": "Intermediate", "is_free": False,
        "description": "A case officer explains job-search requirements.",
        "segments": [
            (EN, "Case officer", "You need to apply for at least five jobs every fortnight.", [
                ("Apply for at least five jobs", "आपको कम से कम पाँच नौकरियों के लिए आवेदन करना होगा"),
                ("Every fortnight", "हर दो हफ़्ते में", "हर हफ़्ते में")]),
            (LOTE, "Client", "मैं हफ़्ते में तीन दिन अपने बच्चों की देखभाल करता हूँ।", [
                ("Cares for children three days a week", "i look after my children three days a week")]),
            (EN, "Case officer", "In that case you can apply for part-time work only.", [
                ("Can apply for part-time work only", "ऐसी स्थिति में आप केवल पार्ट-टाइम काम के लिए आवेदन कर सकते हैं")]),
            (LOTE, "Client", "बहुत अच्छा। मैं आज ही आवेदन शुरू करूँगा।", [
                ("Very good", "very good"),
                ("Will start applying today", "i will start applying today")]),
        ],
    },
    {
        "key": "demo-zh-school-enrolment", "lote": "zh", "title": "DEMO School enrolment", "topic": "Education",
        "difficulty": "Easy", "is_free": False,
        "description": "A teacher explains a new student's first day.",
        "segments": [
            (EN, "Teacher", "Your son can start school next Monday. Classes begin at 8:45.", [
                ("Son can start next Monday", "您的儿子下周一可以开始上学"),
                ("Classes begin at 8:45", "八点四十五分开始上课")]),
            (LOTE, "Parent", "他需要穿校服吗？我们在哪里可以买到？", [
                ("Does he need a uniform", "does he need to wear a uniform"),
                ("Where to buy it", "where can we buy it")]),
            (EN, "Teacher", "Yes. You can buy the uniform at the school office on Wednesday afternoons.", [
                ("Yes", "需要"),
                ("Buy at the school office on Wednesday afternoons", "您可以在每周三下午到学校办公室购买校服")]),
            (LOTE, "Parent", "好的，谢谢您。我们星期三下午去。", [
                ("Okay, thanks", "okay thank you"),
                ("Will go on Wednesday afternoon", "we will go on wednesday afternoon")]),
        ],
    },
    {
        "key": "demo-pa-car-insurance", "lote": "pa", "title": "DEMO Car insurance claim", "topic": "Insurance",
        "difficulty": "Intermediate", "is_free": False,
        "description": "An insurer takes details of a car accident.",
        "segments": [
            (EN, "Insurer", "Was anyone injured in the accident?", [
                ("Was anyone injured", "ਕੀ ਹਾਦਸੇ ਵਿੱਚ ਕਿਸੇ ਨੂੰ ਸੱਟ ਲੱਗੀ ਸੀ")]),
            (LOTE, "Client", "ਨਹੀਂ, ਪਰ ਮੇਰੀ ਕਾਰ ਦਾ ਪਿਛਲਾ ਹਿੱਸਾ ਬੁਰੀ ਤਰ੍ਹਾਂ ਨੁਕਸਾਨਿਆ ਗਿਆ।", [
                ("No one was injured", "no"),
                ("The back of the car was badly damaged", "but the back of my car was badly damaged")]),
            (EN, "Insurer", "Please send us photos of the damage and the other driver's details.", [
                ("Send photos of the damage", "ਕਿਰਪਾ ਕਰਕੇ ਸਾਨੂੰ ਨੁਕਸਾਨ ਦੀਆਂ ਫ਼ੋਟੋਆਂ ਭੇਜੋ"),
                ("And the other driver's details", "ਅਤੇ ਦੂਜੇ ਡਰਾਈਵਰ ਦੀ ਜਾਣਕਾਰੀ ਭੇਜੋ")]),
            (LOTE, "Client", "ਮੈਂ ਅੱਜ ਸ਼ਾਮ ਨੂੰ ਈਮੇਲ ਕਰ ਦਿਆਂਗਾ।", [
                ("Will email them this evening", "i will email them this evening")]),
        ],
    },
    {
        "key": "demo-ar-centrelink-payment", "lote": "ar", "title": "DEMO Stopped payment", "topic": "Social Services",
        "difficulty": "Intermediate", "is_free": False,
        "description": "An officer explains why a payment was stopped.",
        "segments": [
            (EN, "Officer", "Your payment was stopped because we did not receive your income report.", [
                ("Payment was stopped", "تم إيقاف دفعتك"),
                ("Because the income report was not received", "لأننا لم نستلم تقرير دخلك")]),
            (LOTE, "Client", "لقد أرسلت التقرير يوم الاثنين عبر الإنترنت.", [
                ("Sent the report online on Monday", "i sent the report online on monday")]),
            (EN, "Officer", "I can see it now. Your payment will be made within two business days.", [
                ("Can see it now", "أستطيع رؤيته الآن"),
                ("Paid within two business days", "سيتم دفع مستحقاتك خلال يومي عمل")]),
            (LOTE, "Client", "شكراً جزيلاً. هل سأحصل على المبلغ كاملاً؟", [
                ("Thanks", "thank you very much"),
                ("Will the full amount be paid", "will i receive the full amount")]),
        ],
    },
    {
        "key": "demo-ne-bank-account", "lote": "ne", "title": "DEMO Opening a bank account", "topic": "Financial",
        "difficulty": "Easy", "is_free": False,
        "description": "A bank officer explains the documents needed to open an account.",
        "segments": [
            (EN, "Bank officer", "To open an account, we need your passport and proof of address.", [
                ("To open an account", "खाता खोल्नका लागि"),
                ("Need passport and proof of address", "हामीलाई तपाईंको राहदानी र ठेगानाको प्रमाण चाहिन्छ")]),
            (LOTE, "Client", "मसँग राहदानी छ, तर ठेगानाको प्रमाण छैन।", [
                ("Has a passport", "i have my passport"),
                ("No proof of address", "but i don't have proof of address")]),
            (EN, "Bank officer", "A letter from your employer or a utility bill is fine.", [
                ("Employer letter or utility bill is fine", "तपाईंको रोजगारदाताको पत्र वा बिजुली पानीको बिल भए पनि हुन्छ")]),
            (LOTE, "Client", "ठीक छ, म भोलि बिल लिएर आउँछु।", [
                ("Okay", "okay"),
                ("Will bring a bill tomorrow", "i will bring a bill tomorrow")]),
        ],
    },
    {
        "key": "demo-vi-hospital-discharge", "lote": "vi", "title": "DEMO Hospital discharge", "topic": "Health",
        "difficulty": "Easy", "is_free": False,
        "description": "A nurse gives discharge instructions after surgery.",
        "segments": [
            (EN, "Nurse", "You can go home today, but you must rest for one week.", [
                ("Can go home today", "hôm nay ông có thể về nhà"),
                ("Must rest for one week", "nhưng ông phải nghỉ ngơi một tuần")]),
            (LOTE, "Patient", "Tôi có được tắm không? Vết mổ có bị ướt được không?", [
                ("Can I shower", "can i have a shower"),
                ("Can the wound get wet", "can the wound get wet")]),
            (EN, "Nurse", "You can shower after two days. Keep the dressing dry.", [
                ("Shower after two days", "ông có thể tắm sau hai ngày"),
                ("Keep the dressing dry", "hãy giữ băng gạc khô ráo")]),
            (LOTE, "Patient", "Cảm ơn cô. Khi nào tôi cần tái khám?", [
                ("Thanks", "thank you"),
                ("When is the follow-up", "when do i need a follow-up appointment")]),
        ],
    },
]

MOCK_TESTS = [
    {"key": "demo-mock-filipino-1", "title": "DEMO Filipino mock test 1",
     "dialogues": ["demo-fil-medical-appointment", "demo-fil-rental-bond"]},
    {"key": "demo-mock-hindi-1", "title": "DEMO Hindi mock test 1", "dialogues": ["demo-hi-pharmacy", "demo-hi-job-centre"]},
]

# Language-quality errors the demo can show: (wrong phrase a student says, suggested version, explanation).
GRAMMAR_SLIPS = {
    "i work in the mornings": ("i working in the mornings", "I work in the mornings.",
                               "Verb form: 'I working' is missing the auxiliary; use the simple present 'I work'."),
    "i will start applying today": ("i will starting apply today", "I will start applying today.",
                                    "Verb form: after 'will' use the base form 'start', then 'applying'."),
}

# ------------------------------------------------------------------ courses (text only; no fake videos)

def _p(*paras: str) -> str:
    return "".join(f"<p>{x}</p>" for x in paras)


COURSES = [
    {
        "key": "demo-intro-ccl", "title": "DEMO Introduction to the CCL test", "lote": None, "is_free": True,
        "description": ("What the CCL test is, how it is marked, and the core interpreting skills. "
                        "(Demo course: replace with Benchmark's own lessons.)"),
        "chapters": [
            ("CCL Test Overview", [
                ("What is the CCL test?", _p(
                    "The Credentialed Community Language (CCL) test from NAATI checks whether you can interpret a "
                    "conversation between an English speaker and a speaker of your language.",
                    "You hear two dialogues. Each is split into short segments; after each segment there is a chime and "
                    "you interpret what you heard into the other language.")
                 + "<h3>In this lesson you will learn</h3><ul><li>How the test is structured</li>"
                   "<li>What happens after the chime</li><li>How your answers are recorded</li></ul>"),
                ("Test format and scoring", _p(
                    "Each dialogue is marked out of 45, so the test is out of 90. To pass you need 63 in total and at "
                    "least 29 in each dialogue.",
                    "Marks are deducted for three things: accuracy and completeness (each meaning unit you miss or "
                    "change), language quality, and fluency (long pauses, a slow start, hesitations, self-corrections).")),
            ]),
            ("Interpreting Skills", [
                ("Meaning units", _p(
                    "A meaning unit is one piece of information that must come across: who, what, when, where, how much.",
                    "In 'Your appointment is on Tuesday at 10:30 in the morning' the meaning units are the appointment, "
                    "Tuesday, 10:30, and in the morning. Missing or changing any one of them costs a mark.",
                    "Interpret the meaning, not word for word: many wordings are correct if every unit is there.")),
                ("Accuracy, language and fluency", _p(
                    "Accuracy: keep every meaning unit and do not add information that was not said.",
                    "Language: use natural grammar and the right level of politeness for the situation.",
                    "Fluency: start within five seconds of the chime and avoid pauses longer than three seconds.")),
            ]),
        ],
    },
    {
        "key": "demo-exam-prep-filipino", "title": "DEMO Exam preparation (Filipino)", "lote": "fil", "is_free": False,
        "description": "Vocabulary and strategy for the Filipino CCL test. (Demo course: replace with Benchmark's own lessons.)",
        "free_first_lesson": True,
        "chapters": [
            ("Health vocabulary", [
                ("At the clinic", "<h3>Useful terms</h3><table><tr><th>English</th><th>Filipino</th></tr>"
                 "<tr><td>appointment</td><td>appointment / takdang oras</td></tr>"
                 "<tr><td>prescription</td><td>reseta</td></tr><tr><td>blood pressure</td><td>presyon ng dugo</td></tr>"
                 "<tr><td>Medicare card</td><td>Medicare card</td></tr></table>"
                 + _p("Common English loanwords (appointment, form, schedule) are acceptable in Filipino.")),
            ]),
            ("Test strategy", [
                ("Note-taking and politeness", _p(
                    "Note numbers, days and names first: they are the meaning units most often lost.",
                    "Use po and opo when speaking to the professional or an older client: a casual rendering can be a "
                    "register error.")),
            ]),
        ],
    },
]

# ------------------------------------------------------------------ learning hub

HUB = [
    {"key": "demo-note-taking-tips", "title": "DEMO Note-taking tips for the CCL test", "type": "Article", "lote": None,
     "topic": None, "is_free": True, "description": "Five habits that stop you losing meaning units.",
     "html": "<ol><li>Write numbers and times as digits.</li><li>Use symbols: → for 'go', ? for questions.</li>"
             "<li>Note names exactly as heard.</li><li>Leave space between ideas.</li>"
             "<li>Start speaking within five seconds of the chime.</li></ol>"},
    {"key": "demo-naati-practice-test", "title": "NAATI CCL practice test (official)", "type": "Link", "lote": None,
     "topic": None, "is_free": True, "description": "NAATI's own sample of the test. (Demo resource.)",
     "url": "https://www.naati.com.au/ccl-practice-test/"},
    {"key": "demo-health-glossary-fil", "title": "DEMO Health glossary (English-Filipino)", "type": "Glossary", "lote": "fil",
     "topic": "Health", "is_free": False, "description": "A short sample glossary as a PDF.",
     "pdf_lines": ["DEMO Health glossary (English - Filipino)", "", "appointment - takdang oras",
                   "prescription - reseta", "blood pressure - presyon ng dugo", "pharmacy - parmasya",
                   "", "Sample file for the demo. Replace with Benchmark's glossary."]},
    {"key": "demo-legal-glossary-hi", "title": "DEMO Legal terms (English-Hindi)", "type": "Glossary", "lote": "hi",
     "topic": "Legal", "is_free": False, "description": "Common legal terms with Hindi equivalents.",
     "html": "<table><tr><th>English</th><th>Hindi</th></tr><tr><td>lawyer</td><td>वकील</td></tr>"
             "<tr><td>court</td><td>अदालत</td></tr><tr><td>fine</td><td>जुर्माना</td></tr>"
             "<tr><td>witness</td><td>गवाह</td></tr></table>"},
]

# ------------------------------------------------------------------ students (example.com addresses only)

STUDENTS = [
    {"email": "demo.active@example.com", "first": "Demo", "last": "Active", "lote": "fil", "access": "Active",
     "attempts": [("practice", "demo-fil-medical-appointment", "good"), ("practice", "demo-fil-medical-appointment", "excellent"),
                  ("mock", "demo-mock-filipino-1", "mixed")]},
    {"email": "demo.trial@example.com", "first": "Demo", "last": "Trial", "lote": "hi", "access": "Trial", "trial_days": 14,
     "attempts": [("practice", "demo-hi-pharmacy", "weak")]},
    {"email": "demo.free@example.com", "first": "Demo", "last": "Free", "lote": "zh", "access": "None", "attempts": []},
    {"email": "demo.expired@example.com", "first": "Demo", "last": "Expired", "lote": "ar", "access": "Trial", "trial_days": -1,
     "attempts": []},
]
