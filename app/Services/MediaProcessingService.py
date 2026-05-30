# app/Services/MediaProcessingService.py
"""
Pure ffmpeg work — fps detection, audio extraction, duration probing.
No transport, no S3, no Kafka. Just calls ffmpeg/ffprobe.
"""
import os
import json
import subprocess

from app.Config.Config import config


class MediaProcessingService:

    def get_video_fps(self, video_path: str) -> float:
        """Detect video frame rate using ffprobe."""
        cmd = [
            config.FFPROBE_PATH,
            "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "csv=p=0",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(
                "Could not detect video frame rate. "
                "Ensure the file is a valid video with a standard frame rate "
                "(24, 25, 29.97, etc.)."
            )

        raw = result.stdout.strip()
        try:
            if "/" in raw:
                num, den = raw.split("/")
                fps = float(num) / float(den)
            else:
                fps = float(raw)
        except Exception as e:
            raise RuntimeError(f"Could not parse frame rate ({raw}): {e}")

        if fps <= 0:
            raise RuntimeError(f"Invalid frame rate: {fps} fps")
        return fps

    def get_duration(self, input_path: str) -> float:
        """Return duration in seconds via ffprobe."""
        cmd = [
            config.FFPROBE_PATH,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            input_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])

    def extract_audio(self, input_path: str, output_path: str) -> str:
        """Extract audio → 16kHz mono WAV."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cmd = [
            config.FFMPEG_PATH,
            "-i", input_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(config.SAMPLE_RATE),
            "-ac", "1",
            "-y",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr}")
        return output_path