"""
Media Chunker — FPS utilities only.
Chunking removed: transcription worker processes full audio via HuggingFace pipeline.
Keeps get_video_fps() and snap_to_frame() for frame-accurate timestamp handling.
"""
import subprocess
from app.Config import config


def get_video_fps(video_path: str) -> float:
    """Detect video frame rate using ffprobe. Raises with a clear message if not detectable."""
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
            "Could not detect the video frame rate. "
            "Please ensure your file is a valid video with a standard frame rate (e.g. 24, 25, 29.97 fps)."
        )
    try:
        raw = result.stdout.strip()
        if "/" in raw:
            num, den = raw.split("/")
            fps = float(num) / float(den)
        else:
            fps = float(raw)
        if fps <= 0:
            raise RuntimeError(
                f"Invalid video frame rate detected ({fps} fps). "
                "Please ensure your file is a valid video with a standard frame rate (e.g. 24, 25, 29.97 fps)."
            )
        return fps
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Could not read the video frame rate ({e}). "
            "Please ensure your file is a valid video with a standard frame rate (e.g. 24, 25, 29.97 fps)."
        )


def snap_to_frame(seconds: float, fps: float) -> float:
    """Snap a timestamp to the nearest video frame boundary."""
    frame = round(seconds * fps)
    return frame / fps
