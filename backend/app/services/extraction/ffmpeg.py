import subprocess
import json
import os


def get_video_metadata(video_path: str) -> dict:
    """Extract duration, fps, resolution via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe error: {result.stderr}")

    data = json.loads(result.stdout)
    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        None,
    )

    duration = float(data.get("format", {}).get("duration", 0))
    fps = None
    resolution = None

    if video_stream:
        r_frame_rate = video_stream.get("r_frame_rate", "0/1")
        num, den = r_frame_rate.split("/")
        fps = round(int(num) / int(den), 2) if int(den) else None
        w = video_stream.get("width")
        h = video_stream.get("height")
        if w and h:
            resolution = f"{w}x{h}"

    return {"duration_seconds": duration, "fps": fps, "resolution": resolution}


def extract_audio(video_path: str, output_dir: str) -> str:
    """Extract audio as 16kHz mono WAV — the format faster-whisper expects."""
    base = os.path.splitext(os.path.basename(video_path))[0]
    audio_path = os.path.join(output_dir, f"{base}_audio.wav")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",                   # no video
        "-acodec", "pcm_s16le",  # 16-bit PCM
        "-ar", "16000",          # 16 kHz sample rate
        "-ac", "1",              # mono
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error: {result.stderr}")

    return audio_path
