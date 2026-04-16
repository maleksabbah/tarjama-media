"""
Audio Chunker
Split audio into chunks for parallel transcription.
Uses silence detection to find natural break points.
Falls back to fixed-duration splits if silence detection fails.
Frame-accurate chunking: all boundaries snapped to video frame grid.
Saves chunks_meta.json with absolute MP4 timestamps for each chunk.
"""
import os
import subprocess
import json
from app.Config import config
from app.Extractor import get_duration


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


def detect_silence(audio_path: str, min_silence_duration: float = 0.5,
                   silence_threshold: str = "-30dB") -> list[float]:
    """Detect silence points in audio using FFmpeg silencedetect filter."""
    cmd = [
        config.FFMPEG_PATH,
        "-i", audio_path,
        "-af", f"silencedetect=noise={silence_threshold}:d={min_silence_duration}",
        "-f", "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    silence_points = []
    for line in result.stderr.split("\n"):
        if "silence_end" in line:
            try:
                parts = line.split("silence_end: ")[1]
                timestamp = float(parts.split("|")[0].strip())
                silence_points.append(timestamp)
            except (IndexError, ValueError):
                continue
    return silence_points


def find_split_points(duration: float, silence_points: list[float],
                      target_duration: int = None,
                      fps: float = 24.0) -> list[float]:
    """
    Find split points aligned to video frames.
    Falls back to hard cut at target_duration if no silence found nearby.
    """
    target = target_duration or config.CHUNK_DURATION_SECONDS
    split_points = []
    current_pos = 0.0

    while current_pos + target < duration:
        target_point = current_pos + target
        best_point = target_point
        best_distance = float("inf")

        for sp in silence_points:
            if sp <= current_pos:
                continue
            distance = abs(sp - target_point)
            if distance < best_distance and distance < 5.0:
                best_point = sp
                best_distance = distance

        best_point = snap_to_frame(best_point, fps)
        split_points.append(best_point)
        current_pos = best_point

    return split_points


def split_audio(audio_path: str, output_dir: str, job_id: str,
                split_points: list[float] = None,
                duration: float = None,
                fps: float = 24.0) -> tuple[list[str], list[dict]]:
    """
    Split audio file at the given split points.
    Returns:
        chunk_paths: list of local chunk file paths
        chunks_meta: list of dicts with chunk index, absolute_start, absolute_end, duration
    """
    os.makedirs(output_dir, exist_ok=True)

    if not split_points:
        if not duration:
            duration = get_duration(audio_path)
        target = config.CHUNK_DURATION_SECONDS
        split_points = []
        pos = snap_to_frame(target, fps)
        while pos < duration:
            split_points.append(pos)
            pos = snap_to_frame(pos + target, fps)

    boundaries = [0.0] + split_points + [duration if duration else None]
    chunk_paths = []
    chunks_meta = []

    for i in range(len(boundaries) - 1):
        start = snap_to_frame(boundaries[i], fps)
        end = boundaries[i + 1]
        if end is not None:
            end = snap_to_frame(end, fps)

        chunk_filename = f"chunk_{i:04d}.wav"
        chunk_path = os.path.join(output_dir, chunk_filename)

        cmd = [
            config.FFMPEG_PATH,
            "-i", audio_path,
            "-ss", f"{start:.6f}",
        ]
        if end is not None:
            cmd.extend(["-to", f"{end:.6f}"])
        cmd.extend([
            "-acodec", "pcm_s16le",
            "-ar", str(config.SAMPLE_RATE),
            "-ac", "1",
            "-y",
            chunk_path,
        ])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  [CHUNKER] Warning: Failed to create chunk {i}: {result.stderr[:200]}")
            continue

        if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 1000:
            chunk_paths.append(chunk_path)
            actual_end = end if end is not None else start + get_duration(chunk_path)
            chunks_meta.append({
                "chunk_index": i,
                "absolute_start": start,
                "absolute_end": actual_end,
                "duration": actual_end - start,
                "fps": fps,
            })

    return chunk_paths, chunks_meta
