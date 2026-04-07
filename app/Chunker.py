"""
Audio Chunker
Split audio into chunks for parallel transcription.
Uses silence detection to find natural break points.
Falls back to fixed-duration splits if silence detection fails.
"""
import os
import subprocess
import json
from app.Config import config
from app.Extractor import get_duration
def detect_silence(audio_path:str,min_silence_duration:float=0.5,
                   silence_threshold:str= "-30dB")->list[float]:
    """Detect silence points in audio using FFmpeg silencedetect filter."""
    cmd = [
        config.FFMPEG_PATH,
        "-i", audio_path,
        "-af", f"silencedetect=noise={silence_threshold}:d={min_silence_duration}",
        "-f", "null",
        "-",
    ]
    result = subprocess.run(cmd,capture_output=True,text=True)
    # Parse silence_end timestamps from stderr
    silence_points = []
    for line in result.stderr.split("\n"):
        if "silence_end" in line:
            try:
                parts = line.split("silence_end: ")[1]
                timestamp = float(parts.split("|")[0].strip())
                silence_points.append(timestamp)
            except(IndexError,ValueError):
                continue
    return silence_points
def find_split_points(duration: float, silence_points: list[float],
                      target_duration: int = None) -> list[float]:
    target = target_duration or config.CHUNK_DURATION_SECONDS
    split_points = []
    current_pos = 0

    while current_pos + target < duration:
        target_point = current_pos + target
        best_point = target_point
        best_distance = float("inf")

        for sp in silence_points:                              # inside while
            if sp <= current_pos:                              # inside for
                continue                                       # inside for
            distance = abs(sp - target_point)                  # inside for
            if distance < best_distance and distance < 5.0:    # inside for
                best_point = sp                                # inside if
                best_distance = distance                       # inside if
        split_points.append(best_point)                        # inside while, outside for
        current_pos = best_point                               # inside while, outside for

    return split_points

def split_audio(audio_path: str, output_dir: str, job_id: str,
                split_points: list[float] = None,
                duration: float = None) -> list[str]:
    """Split audio file at the given split points. Returns list of chunk paths."""
    os.makedirs(output_dir, exist_ok=True)

    if not split_points:
        # Fixed duration fallback
        if not duration:
            duration = get_duration(audio_path)
        target = config.CHUNK_DURATION_SECONDS
        split_points = []
        pos = target
        while pos < duration:
            split_points.append(pos)
            pos += target
    # Build segment boundaries
    boundaries = [0.0] + split_points + [None]
    chunk_paths = []

    for i in range(len(boundaries)-1):
        start = boundaries[i]
        end = boundaries[i+1]
        chunk_filename = f"chunk_{i:04d}.wav"
        chunk_path = os.path.join(output_dir, chunk_filename)

        cmd = [
            config.FFMPEG_PATH,
            "-i", audio_path,
            "-ss", str(start),
        ]

        if end is not None:
            cmd.extend(["-to", str(end)])
        cmd.extend([
            "-acodec","pcm_s16le",
            "-ar",str(config.SAMPLE_RATE),
            "-ac","1",
            "-y",
            chunk_path,
        ])
        result = subprocess.run(cmd,capture_output=True,text=True)
        if result.returncode != 0:
            print(f"  [CHUNKER] Warning: Failed to create chunk {i}: {result.stderr[:200]}")
            continue
        # Only add if file was created and has content
        if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 1000:
            chunk_paths.append(chunk_path)

    return chunk_paths


















