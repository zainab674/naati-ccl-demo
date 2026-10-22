"""Real-sounding speech for the DEMO data: Microsoft neural voices through edge-tts (free, no key), and Google's
voice through gTTS for Punjabi, which edge-tts does not offer. Development only (requirements-dev.txt).

Clips are cached in backend/data/demo_tts/, so reloading the demo does not download them again. Every function returns
False instead of raising when speech cannot be made (e.g. offline), and the caller falls back to synthetic tones.
"""
import asyncio
import hashlib
import logging
import wave
from pathlib import Path

from .services.media_pipeline import run_ffmpeg
from .settings import BASE_DIR

log = logging.getLogger("demo")
CACHE = BASE_DIR / "data" / "demo_tts"
RATE = 16000

# language -> (female voice, male voice). "gtts:<lang>" uses gTTS (one voice per language).
VOICES = {
    "en": ("en-AU-NatashaNeural", "en-AU-WilliamMultilingualNeural"),
    "fil": ("fil-PH-BlessicaNeural", "fil-PH-AngeloNeural"),
    "hi": ("hi-IN-SwaraNeural", "hi-IN-MadhurNeural"),
    "zh": ("zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"),
    "ar": ("ar-SA-ZariyahNeural", "ar-SA-HamedNeural"),
    "ne": ("ne-NP-HemkalaNeural", "ne-NP-SagarNeural"),
    "vi": ("vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"),
    "pa": ("gtts:pa", "gtts:pa"),
}


def _clip(text: str, voice: str) -> Path | None:
    """16 kHz mono WAV of `text` in `voice`, from the cache or freshly made."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{voice}|{text}".encode()).hexdigest()[:20]
    wav = CACHE / f"{key}.wav"
    if wav.exists():
        return wav
    mp3 = CACHE / f"{key}.mp3"
    try:
        if voice.startswith("gtts:"):
            from gtts import gTTS
            gTTS(text, lang=voice.split(":", 1)[1]).save(str(mp3))
        else:
            import edge_tts
            asyncio.run(edge_tts.Communicate(text, voice).save(str(mp3)))
        run_ffmpeg(["-i", str(mp3), "-ar", str(RATE), "-ac", "1", str(wav)])
    except Exception as e:  # noqa: BLE001 - offline, voice service down, package missing: fall back to tones
        log.warning("speech not available (%s: %s); using synthetic audio", type(e).__name__, str(e)[:120])
        return None
    finally:
        mp3.unlink(missing_ok=True)
    return wav


def _frames(path: Path) -> bytes:
    with wave.open(str(path), "rb") as f:
        return f.readframes(f.getnframes())


def speak(out: Path, parts: list[str], lang: str, female: bool, *, lead: float = 0.3, pause: float = 0.0) -> float | None:
    """Speak `parts` one after another (with `pause` seconds of silence between the first and the rest), after `lead`
    seconds of silence. Returns the duration, or None when speech is not available."""
    voice = VOICES[lang][0 if female else 1]
    clips = []
    for text in parts:
        if text.strip():
            clip = _clip(text, voice)
            if clip is None:
                return None
            clips.append(clip)
    if not clips:
        return None
    silence = lambda s: b"\x00\x00" * int(s * RATE)  # noqa: E731
    pcm = silence(lead) + _frames(clips[0])
    for clip in clips[1:]:
        pcm += silence(pause if pause else 0.15) + _frames(clip)
    pcm += silence(0.4)
    with wave.open(str(out), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(pcm)
    return len(pcm) / 2 / RATE
