"""Audio -> chime appended -> AES-128 encrypted HLS (from the demo), plus a waveform image.

Each segment becomes its own small encrypted HLS stream. There is never a plain audio file in storage or on the
wire: the key is only served through the signed, session-bound media endpoint.
"""
import re
import secrets
import shutil
import subprocess
from pathlib import Path

from ..settings import ccl_config, get_settings

KEY_URI_PLACEHOLDER = "__KEY_URI__"


def ffmpeg_exe() -> str:
    """System ffmpeg in Docker images; the bundled imageio-ffmpeg binary elsewhere (dev on Windows/macOS)."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args: list[str], timeout: int = 180) -> None:
    proc = subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args],
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-800:]}")


def chime_path() -> Path:
    """Two-tone chime, generated once into scratch space."""
    path = get_settings().scratch_dir / "chime.wav"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg([
            "-f", "lavfi", "-i", "sine=frequency=880:duration=0.22",
            "-f", "lavfi", "-i", "sine=frequency=1320:duration=0.38",
            "-filter_complex",
            "[0]afade=t=out:st=0.15:d=0.07[a];[1]afade=t=out:st=0.1:d=0.28[b];[a][b]concat=n=2:v=0:a=1,volume=0.5",
            "-ar", "44100", "-ac", "1", str(path),
        ])
    return path


def package_hls(src_audio: Path, out_dir: Path, append_chime: bool = True) -> float:
    """Encode to AES-128 encrypted HLS in out_dir. Returns the stream duration in seconds."""
    out_dir.mkdir(parents=True, exist_ok=True)
    key_file = out_dir / "enc.key"
    key_file.write_bytes(secrets.token_bytes(16))
    keyinfo = out_dir.parent / f"keyinfo-{secrets.token_hex(4)}.txt"
    keyinfo.write_text(f"{KEY_URI_PLACEHOLDER}\n{key_file.as_posix()}\n{secrets.token_hex(16)}\n", encoding="utf-8")
    inputs = ["-i", str(src_audio)]
    maps: list[str] = []
    if append_chime:
        inputs += ["-i", str(chime_path())]
        gap = ccl_config()["segment"].get("chime_gap_seconds", 0.35)
        maps = ["-filter_complex",
                f"[0]aresample=44100,aformat=channel_layouts=mono,apad=pad_dur={gap}[s];"
                "[1]aresample=44100,aformat=channel_layouts=mono[c];[s][c]concat=n=2:v=0:a=1[out]",
                "-map", "[out]"]
    try:
        run_ffmpeg([
            *inputs, *maps,
            "-vn", "-ac", "1", "-c:a", "aac", "-b:a", "96k",
            "-f", "hls", "-hls_time", "4", "-hls_playlist_type", "vod",
            "-hls_key_info_file", str(keyinfo),
            "-hls_segment_filename", str(out_dir / "s%03d.ts"),
            str(out_dir / "index.m3u8"),
        ])
    finally:
        keyinfo.unlink(missing_ok=True)
    playlist = (out_dir / "index.m3u8").read_text(encoding="utf-8")
    return round(sum(float(x) for x in re.findall(r"#EXTINF:([\d.]+)", playlist)), 2)


def waveform_png(src_audio: Path, out: Path, width: int = 1200, height: int = 160) -> None:
    run_ffmpeg(["-i", str(src_audio), "-filter_complex",
                f"aformat=channel_layouts=mono,showwavespic=s={width}x{height}:colors=0x1f6778",
                "-frames:v", "1", str(out)])


def probe_duration(src_audio: Path) -> float | None:
    """Duration of an audio file in seconds (ffmpeg prints it on stderr)."""
    proc = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(src_audio)], capture_output=True, text=True,
                          timeout=60)
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not m:
        return None
    h, mnt, s = m.groups()
    return round(int(h) * 3600 + int(mnt) * 60 + float(s), 2)
