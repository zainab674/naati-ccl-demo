"""Fluency timing measured by code, never by the model (SCORING_BRIEF.md section 3).

  start delay : first speech in the recording (+ the gap between the chime ending and the recording starting)
                longer than timing.start_delay_seconds -> StartDelay
  pauses      : silence between speech inside the answer longer than timing.long_pause_seconds -> Pause
  fillers     : hesitation-marker words found in the transcript; passed to the AI as candidates (the AI decides
                whether they are genuine hesitation, so they are not deducted here)

Speech is found with a simple energy-based voice activity detector on 16 kHz mono PCM; Whisper word timestamps
are the fallback when the audio cannot be decoded.
"""
import array
import math
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..media_pipeline import ffmpeg_exe

SAMPLE_RATE = 16000
FRAME_MS = 30


@dataclass
class TimingEvent:
    type: str              # "StartDelay" | "Pause"
    start: float           # seconds from the recording start
    duration: float
    explanation: str


@dataclass
class TimingResult:
    speech_regions: list[tuple[float, float]] = field(default_factory=list)
    duration: float = 0.0
    speech_start: float | None = None   # seconds from the chime (recording offset included)
    events: list[TimingEvent] = field(default_factory=list)
    method: str = "vad"                 # vad | words | none
    filler_candidates: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"speech_regions": [[round(a, 2), round(b, 2)] for a, b in self.speech_regions],
                "duration": round(self.duration, 2),
                "speech_start": None if self.speech_start is None else round(self.speech_start, 2),
                "method": self.method, "events": [e.__dict__ for e in self.events],
                "filler_candidates": self.filler_candidates}


def decode_pcm(path: Path) -> array.array:
    proc = subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1",
                           "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"], capture_output=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg decode failed: {proc.stderr[-300:]!r}")
    samples = array.array("h")
    samples.frombytes(proc.stdout[: len(proc.stdout) // 2 * 2])
    return samples


def frame_levels(samples: array.array) -> list[float]:
    """RMS level per 30 ms frame in dBFS."""
    n = SAMPLE_RATE * FRAME_MS // 1000
    levels = []
    for i in range(0, len(samples) - n + 1, n):
        frame = samples[i:i + n]
        rms = math.sqrt(sum(s * s for s in frame) / n) if n else 0
        levels.append(20 * math.log10(rms / 32768) if rms > 0 else -120.0)
    return levels


def speech_regions(levels: list[float], min_speech_ms: int = 120, hangover_ms: int = 240,
                   abs_floor_db: float = -48.0, margin_db: float = 14.0) -> list[tuple[float, float]]:
    """Frames well above the noise floor are speech; short gaps are bridged (hangover), tiny blips dropped."""
    if not levels:
        return []
    ordered = sorted(levels)
    noise_floor = ordered[max(0, int(len(ordered) * 0.1) - 1)]
    threshold = max(abs_floor_db, noise_floor + margin_db)
    frame_s = FRAME_MS / 1000
    regions: list[list[float]] = []
    for i, lvl in enumerate(levels):
        if lvl < threshold:
            continue
        t = i * frame_s
        if regions and t - regions[-1][1] <= hangover_ms / 1000:
            regions[-1][1] = t + frame_s
        else:
            regions.append([t, t + frame_s])
    return [(a, b) for a, b in regions if (b - a) * 1000 >= min_speech_ms]


def regions_from_words(words: list[dict], gap_join: float = 0.25) -> list[tuple[float, float]]:
    regions: list[list[float]] = []
    for w in words:
        s, e = float(w.get("start") or 0), float(w.get("end") or 0)
        if regions and s - regions[-1][1] <= gap_join:
            regions[-1][1] = max(regions[-1][1], e)
        else:
            regions.append([s, e])
    return [(a, b) for a, b in regions]


def recording_offset(timing: dict) -> float:
    """Seconds between the chime ending and the recorder actually starting (client clock), clamped to 0..2 s."""
    try:
        gap = (float(timing["record_start_ms"]) - float(timing["chime_end_ms"])) / 1000
    except (KeyError, TypeError, ValueError):
        return 0.0
    return min(max(gap, 0.0), 2.0)


def timing_events(regions: list[tuple[float, float]], offset: float, cfg: dict) -> tuple[float | None, list[TimingEvent]]:
    delay_limit = float(cfg["start_delay_seconds"])
    pause_limit = float(cfg["long_pause_seconds"])
    cap = cfg.get("max_pause_events_per_segment")
    events: list[TimingEvent] = []
    if not regions:
        return None, events
    speech_start = regions[0][0] + offset
    if speech_start > delay_limit:
        events.append(TimingEvent("StartDelay", 0.0, round(speech_start, 2),
                                  f"You started speaking {speech_start:.1f} s after the chime (limit {delay_limit:g} s)."))
    for (_, end), (start, _) in zip(regions, regions[1:], strict=False):
        gap = start - end
        if gap > pause_limit:
            events.append(TimingEvent("Pause", round(end, 2), round(gap, 2),
                                      f"Pause of {gap:.1f} s while interpreting (limit {pause_limit:g} s)."))
    if cap is not None:
        pauses = [e for e in events if e.type == "Pause"][: int(cap)]
        events = [e for e in events if e.type != "Pause"] + pauses
    return speech_start, events


def filler_candidates(words: list[dict], transcript: str, markers: list[str]) -> list[dict]:
    """Hesitation-marker words with their times. Multi-word markers ("ano ba") are matched in the transcript."""
    single = {m.lower() for m in markers if " " not in m}
    found = []
    for w in words:
        token = re.sub(r"[^\w-]", "", (w.get("word") or "").lower())
        if token in single:
            found.append({"text": token, "start": w.get("start")})
    if not words:
        for token in re.findall(r"[\w-]+", transcript.lower()):
            if token in single:
                found.append({"text": token, "start": None})
    for m in (m.lower() for m in markers if " " in m):
        for _ in re.finditer(rf"(?<!\w){re.escape(m)}(?!\w)", transcript.lower()):
            found.append({"text": m, "start": None})
    return found


def analyse(audio: Path | None, words: list[dict], transcript: str, timing: dict, cfg: dict,
            markers: list[str]) -> TimingResult:
    result = TimingResult()
    regions: list[tuple[float, float]] = []
    if audio is not None:
        try:
            samples = decode_pcm(audio)
            result.duration = len(samples) / SAMPLE_RATE
            regions = speech_regions(frame_levels(samples))
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            regions = []
    if regions:
        result.method = "vad"
    elif words:
        regions, result.method = regions_from_words(words), "words"
    else:
        result.method = "none"
    result.speech_regions = regions
    result.speech_start, result.events = timing_events(regions, recording_offset(timing), cfg)
    result.filler_candidates = filler_candidates(words, transcript, markers)
    return result
