"""Builds the example-segment clip played on the player's equipment check (Information page 2): a short spoken
English sentence in a neural voice, then the test chime, plus its waveform image. Writes into frontend/public/exam/.

    python -m scripts.make_example_segment          (needs requirements-dev.txt: edge-tts)
"""
import sys
import tempfile
from pathlib import Path

from app.demo_voice import speak
from app.services.media_pipeline import chime_path, run_ffmpeg, waveform_png
from app.settings import REPO_DIR

TEXT = [
    "Good morning, and welcome.",
    "This short example lets you check your speakers, microphone and camera before the test.",
    "After the chime, please say this sentence back in your own words.",
]
OUT = REPO_DIR / "frontend" / "public" / "exam"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        speech = Path(tmp) / "speech.wav"
        if speak(speech, TEXT, "en", female=True, lead=0.4, pause=0.35) is None:
            sys.exit("Speech could not be made (offline, or edge-tts missing).")
        mixed = Path(tmp) / "example.wav"
        run_ffmpeg(["-i", str(speech), "-i", str(chime_path()), "-filter_complex",
                    "[0]loudnorm=I=-16:TP=-1.5,aresample=44100,aformat=channel_layouts=mono,apad=pad_dur=0.35[s];"
                    "[1]aresample=44100,aformat=channel_layouts=mono[c];[s][c]concat=n=2:v=0:a=1[out]",
                    "-map", "[out]", str(mixed)])
        run_ffmpeg(["-i", str(mixed), "-ac", "1", "-c:a", "libmp3lame", "-b:a", "96k", str(OUT / "example-segment.mp3")])
        waveform_png(mixed, OUT / "example-waveform.png")
    print("written", OUT / "example-segment.mp3", OUT / "example-waveform.png")


if __name__ == "__main__":
    main()
