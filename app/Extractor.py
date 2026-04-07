"""
Audio Extractor
Extract audio from video files using FFmpeg.
Outputs 16kHz mono WAV (Whisper's expected format).
"""
import os
import subprocess
import json
from app.Config import config

def get_duration(input_path:str) -> float:
    """Get duration of audio using ffmpeg probe."""
    cmd = [
        config.FFPROBE_PATH,
        "-v","quiet",
        "-print_format","json",
        "-show_format",
        input_path,
    ]
    result = subprocess.run(cmd,capture_output=True,text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    info = json.loads(result.stdout)
    return float(info["format"]["duration"])

def extract_audio(input_path:str,output_path:str) -> str:
    """Extract audio from video → 16kHz mono WAV."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        config.FFMPEG_PATH,
        "-i", input_path,
        "-vn",  # no video
        "-acodec", "pcm_s16le",  # 16-bit PCM
        "-ar", str(config.SAMPLE_RATE),  # 16kHz
        "-ac", "1",  # mono
        "-y",  # overwrite
        output_path,
    ]
    result = subprocess.run(cmd,capture_output=True,text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr}")
    return output_path


