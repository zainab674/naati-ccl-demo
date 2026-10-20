"""Languages offered (each LOTE is paired with English) and the starting evaluator guidance per language.

The guidance is a starting point written from general linguistic knowledge. Benchmark's teachers for each language
must review it before scores in that language are relied on (BUILD_PLAN open questions). Edit it in the
language_scoring_configs table; this file only seeds languages that have no config yet.

Codes: ISO 639-1 where it exists (Filipino uses "fil", the code already used by imports). stt_code is the Whisper
language hint.
"""
from .models import LanguageType

LANGUAGES = [
    {"code": "en", "name": "English", "native_name": "English", "language_type": LanguageType.ENGLISH, "stt_code": "en"},
    {"code": "fil", "name": "Filipino", "native_name": "Filipino (Tagalog)", "language_type": LanguageType.LOTE,
     "stt_code": "tl"},
    {"code": "hi", "name": "Hindi", "native_name": "हिन्दी", "language_type": LanguageType.LOTE, "stt_code": "hi"},
    {"code": "zh", "name": "Mandarin", "native_name": "普通话", "language_type": LanguageType.LOTE, "stt_code": "zh"},
    {"code": "pa", "name": "Punjabi", "native_name": "ਪੰਜਾਬੀ", "language_type": LanguageType.LOTE, "stt_code": "pa"},
    {"code": "ar", "name": "Arabic", "native_name": "العربية", "language_type": LanguageType.LOTE, "stt_code": "ar"},
    {"code": "ne", "name": "Nepali", "native_name": "नेपाली", "language_type": LanguageType.LOTE, "stt_code": "ne"},
    {"code": "vi", "name": "Vietnamese", "native_name": "Tiếng Việt", "language_type": LanguageType.LOTE, "stt_code": "vi"},
]

_PRONUNCIATION = {"auto_deduct": False, "review_only": True}
# Fillers common to every language when speakers hesitate in English-influenced speech.
_EN_FILLERS = ["um", "uh", "erm", "hmm"]

SCORING = {
    "fil": {
        "grammar_guidelines": (
            "Filipino (Tagalog) as spoken in community settings. Check verb aspect (perfective/imperfective/"
            "contemplative) matches the time reference, correct focus/affix use, correct markers (ang/ng/sa, si/ni/kay) "
            "and linkers (na/-ng). Do not penalise acceptable spoken variation or common contractions."),
        "register_guidelines": (
            "Use a neutral-professional register suitable for an interpreter. Respect markers (po/opo, kayo/ninyo as "
            "polite forms) are expected when addressing the professional or an older client; a significantly casual "
            "or disrespectful rendering is a register error. Common English loanwords used in everyday Filipino "
            "(appointment, form, bill, schedule) are acceptable and are not errors."),
        "hesitation_markers": ["ah", "eh", "ano", "ano ba", "kuwan", "kwan", "parang", "e", "um", "uh"],
        "ai_prompt_addition": (
            "Code-switching with common English words (Taglish) is normal in Filipino and is not an error as long as "
            "the segment is interpreted into Filipino and the meaning is conveyed. A segment answered fully in English "
            "when Filipino was required is an accuracy problem (meaning not transferred into the target language)."),
    },
    "hi": {
        "grammar_guidelines": (
            "Standard spoken Hindi. Check gender and number agreement of verbs, adjectives and postpositions "
            "(का/की/के), the ergative ने with transitive perfective verbs, correct tense and aspect, and correct "
            "postpositions (को, में, से, पर). Do not penalise acceptable regional variation in everyday speech."),
        "register_guidelines": (
            "Use आप (not तुम/तू) for the client and the professional, with matching verb forms (आप जाइए / आप जाते हैं). "
            "Overly casual or disrespectful forms are a register error. Very formal Sanskritised vocabulary is not "
            "required; everyday words are fine."),
        "hesitation_markers": ["मतलब", "यानी", "वो", "अं", "अ", "हम्म", "क्या कहते हैं", "matlab", "yaani", *_EN_FILLERS],
        "ai_prompt_addition": (
            "English loanwords common in everyday Hindi (appointment, form, doctor, bill, test) are acceptable and are "
            "not errors. A segment answered fully in English when Hindi was required is an accuracy problem. The "
            "transcript may mix Devanagari and Latin script; script choice is not an error."),
    },
    "zh": {
        "grammar_guidelines": (
            "Standard spoken Mandarin (Putonghua). Check word order, correct measure words (量词), aspect particles "
            "(了/过/着), correct use of 的/得/地 in meaning, and complete sentence structure. Do not penalise "
            "acceptable spoken variation."),
        "register_guidelines": (
            "Use 您 for the professional and older clients where appropriate, and a polite, neutral tone. Overly "
            "casual or rude phrasing is a register error."),
        "hesitation_markers": ["嗯", "呃", "额", "那个", "这个", "就是说", *_EN_FILLERS],
        "ai_prompt_addition": (
            "The transcript may be in simplified or traditional characters; the character set is not an error. "
            "Chinese has no spaces between words: quote the student's words exactly as they appear in the transcript. "
            "A segment answered fully in English when Mandarin was required is an accuracy problem."),
    },
    "pa": {
        "grammar_guidelines": (
            "Standard spoken Punjabi. Check gender and number agreement, the ergative ਨੇ with transitive perfective "
            "verbs, correct tense and postpositions (ਦਾ/ਦੀ/ਦੇ, ਨੂੰ, ਵਿੱਚ, ਤੋਂ). Do not penalise acceptable regional "
            "variation (e.g. Majhi, Doabi, Malwai)."),
        "register_guidelines": (
            "Use ਤੁਸੀਂ (not ਤੂੰ) with matching verb forms for the client and the professional, with respectful forms "
            "such as ਜੀ where natural. Overly casual or disrespectful forms are a register error."),
        "hesitation_markers": ["ਮਤਲਬ", "ਯਾਨੀ", "ਉਹ", "ਅ", "ਹੈਂ", "مطلب", "matlab", *_EN_FILLERS],
        "ai_prompt_addition": (
            "The transcript may be in Gurmukhi or Shahmukhi script, or romanised; script choice is not an error. "
            "English loanwords common in everyday Punjabi are acceptable. A segment answered fully in English when "
            "Punjabi was required is an accuracy problem."),
    },
    "ar": {
        "grammar_guidelines": (
            "Spoken Arabic as used in community interpreting. Both Modern Standard Arabic and widely understood "
            "dialects (e.g. Levantine, Egyptian, Iraqi, Gulf) are acceptable. Check gender and number agreement, "
            "verb conjugation for person and tense, correct pronoun suffixes and complete sentence structure. Do not "
            "treat dialect features as grammar errors, but do flag an inconsistent mix that obscures meaning."),
        "register_guidelines": (
            "Use a polite, neutral-professional register (e.g. حضرتك / حضرتِك, أستاذ, or respectful plural forms where "
            "customary). Rude or overly casual phrasing is a register error."),
        "hesitation_markers": ["يعني", "اه", "آه", "امم", "إمم", "هيك", "ya'ni", *_EN_FILLERS],
        "ai_prompt_addition": (
            "Arabic is written right to left; quote the student's words exactly as they appear in the transcript. "
            "Diacritics may be missing from the transcript; their absence is not an error. A segment answered fully "
            "in English when Arabic was required is an accuracy problem."),
    },
    "ne": {
        "grammar_guidelines": (
            "Standard spoken Nepali. Check verb agreement with person, number, gender and honorific level, the "
            "ergative ले with transitive past verbs, correct tense and postpositions (को, लाई, मा, बाट). Do not "
            "penalise acceptable regional variation."),
        "register_guidelines": (
            "Use तपाईं (not तिमी/तँ) with matching verb forms for the client and the professional; हजुर is also "
            "acceptable. Overly casual or disrespectful forms are a register error."),
        "hesitation_markers": ["मतलब", "अनि", "त्यो", "के भन्ने", "अँ", "अ", *_EN_FILLERS],
        "ai_prompt_addition": (
            "English loanwords common in everyday Nepali are acceptable and are not errors. The transcript may mix "
            "Devanagari and Latin script; script choice is not an error. A segment answered fully in English when "
            "Nepali was required is an accuracy problem."),
    },
    "vi": {
        "grammar_guidelines": (
            "Standard spoken Vietnamese (northern or southern varieties are both acceptable). Check word order, "
            "classifiers, time and aspect markers (đã/đang/sẽ), and complete sentence structure. Missing tone marks "
            "in the transcript are a transcription issue, not a grammar error."),
        "register_guidelines": (
            "Use appropriate kinship pronouns and polite particles for the professional and the client (e.g. "
            "anh/chị/ông/bà with ạ). Using mày/tao or omitting expected politeness to an older client is a register "
            "error."),
        "hesitation_markers": ["ờ", "ừ", "ừm", "à", "thì", "kiểu", "cái", *_EN_FILLERS],
        "ai_prompt_addition": (
            "Some hesitation markers (à, thì, cái) are also ordinary words; only treat them as hesitation when they "
            "are fillers. A segment answered fully in English when Vietnamese was required is an accuracy problem."),
    },
}

for _cfg in SCORING.values():
    _cfg.setdefault("pronunciation_config", _PRONUNCIATION)
