"""Content pipeline: script text -> TTS -> + chime -> AES-128 encrypted HLS.

Each dialogue segment becomes its own tiny encrypted HLS stream under
data/media/<activity_id>/<segment_order>/. The raw TTS file is deleted after
packaging, so there is never a plain mp3 on disk or on the wire.
"""
import asyncio
import os
import re
import secrets
import shutil
import subprocess
from pathlib import Path

import edge_tts
import imageio_ffmpeg

from ..settings import ccl_config, get_settings

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
KEY_URI_PLACEHOLDER = "__KEY_URI__"


def _run(args: list[str]) -> None:
    proc = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-800:]}")


def chime_path() -> Path:
    """Two-tone chime, generated once."""
    path = get_settings().media_dir / "chime.wav"
    if not path.exists():
        _run([
            "-f", "lavfi", "-i", "sine=frequency=880:duration=0.22",
            "-f", "lavfi", "-i", "sine=frequency=1320:duration=0.38",
            "-filter_complex",
            "[0]afade=t=out:st=0.15:d=0.07[a];[1]afade=t=out:st=0.1:d=0.28[b];"
            "[a][b]concat=n=2:v=0:a=1,volume=0.5",
            "-ar", "44100", "-ac", "1", str(path),
        ])
    return path


def tts_to_file(text: str, voice: str, out: Path, rate: str = "+0%") -> None:
    async def _go():
        await edge_tts.Communicate(text, voice, rate=rate).save(str(out))
    asyncio.run(_go())


def voice_for(language: str, gender: str) -> str:
    return ccl_config()["voices"][language][gender]


def package_hls(src_audio: Path, out_dir: Path, append_chime: bool = True) -> float:
    """Encode to AES-128 encrypted HLS. Returns duration in seconds."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*"):
        old.unlink()
    key_file = out_dir / "enc.key"
    key_file.write_bytes(secrets.token_bytes(16))
    iv = secrets.token_hex(16)
    keyinfo = out_dir / "keyinfo.txt"
    keyinfo.write_text(f"{KEY_URI_PLACEHOLDER}\n{key_file.as_posix()}\n{iv}\n", encoding="utf-8")

    inputs = ["-i", str(src_audio)]
    if append_chime:
        inputs += ["-i", str(chime_path())]
        # short gap between speech and chime
        filt = "[0]aresample=44100,apad=pad_dur=0.35[s];[1]aresample=44100[c];[s][c]concat=n=2:v=0:a=1[out]"
        maps = ["-filter_complex", filt, "-map", "[out]"]
    else:
        maps = []
    _run([
        *inputs, *maps,
        "-ac", "1", "-c:a", "aac", "-b:a", "96k",
        "-f", "hls", "-hls_time", "4", "-hls_playlist_type", "vod",
        "-hls_key_info_file", str(keyinfo),
        "-hls_segment_filename", str(out_dir / "s%03d.ts"),
        str(out_dir / "index.m3u8"),
    ])
    keyinfo.unlink()
    playlist = (out_dir / "index.m3u8").read_text(encoding="utf-8")
    return round(sum(float(x) for x in re.findall(r"#EXTINF:([\d.]+)", playlist)), 2)


def build_segment_media(activity_id: str, order: int, text: str, voice: str) -> tuple[str, float]:
    """Returns (asset_key, duration)."""
    settings = get_settings()
    asset_key = f"{activity_id}/{order:02d}"
    out_dir = settings.media_dir / asset_key
    tmp = settings.data_dir / "tmp" / f"{activity_id}-{order}-{secrets.token_hex(4)}.mp3"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        tts_to_file(text, voice, tmp)
        duration = package_hls(tmp, out_dir)
    finally:
        if tmp.exists():
            os.remove(tmp)
    return asset_key, duration


def synthesize_student_answer(text: str, language: str, out: Path) -> None:
    """Seed helper: fake a candidate's recorded answer with an Indian-accent voice."""
    cfg = ccl_config()["voices"]
    voice = cfg["student_en"] if language == "en" else cfg["student_hi"]
    out.parent.mkdir(parents=True, exist_ok=True)
    tts_to_file(text, voice, out, rate="-8%")


def remove_activity_media(activity_id: str) -> None:
    shutil.rmtree(get_settings().media_dir / activity_id, ignore_errors=True)
