"""
Media Worker (S3 version)
Pop task → download video from S3 → extract audio → detect FPS → upload to S3 → push completion.
No chunking — full audio is sent to transcription worker directly.
"""
import os
import json
import subprocess
import tempfile
from app.Config import config
from app import Redis_client as rc
from app import S3_client as s3
from app.Extractor import extract_audio, get_duration


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


async def process_task(message: dict):
    task_id = message["task_id"]
    job_id = message["job_id"]
    input_s3_key = message["input_path"]

    print(f"  [MEDIA] Processing job {job_id}: {input_s3_key}")

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Step 1: Download video from S3
            local_video = os.path.join(tmp_dir, "video.mp4")
            print(f"  [MEDIA] Downloading video from S3...")
            s3.download_file(input_s3_key, local_video)

            # Step 2: Detect FPS
            fps = get_video_fps(local_video)
            print(f"  [MEDIA] Detected FPS: {fps:.3f}")

            # Step 3: Extract full audio → 16kHz mono WAV
            local_audio = os.path.join(tmp_dir, "full_audio.wav")
            print(f"  [MEDIA] Extracting audio...")
            extract_audio(local_video, local_audio)

            # Step 4: Get duration
            duration = get_duration(local_audio)
            print(f"  [MEDIA] Duration: {duration:.1f}s")

            # Step 5: Upload full audio to S3
            audio_s3_key = f"audio/{job_id}/full_audio.wav"
            s3.upload_file(local_audio, audio_s3_key)
            print(f"  [MEDIA] Uploaded full audio")

            # Step 6: Save and upload video_meta.json
            meta = {"fps": fps, "duration": duration, "job_id": job_id}
            meta_path = os.path.join(tmp_dir, "video_meta.json")
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
            meta_s3_key = f"audio/{job_id}/video_meta.json"
            s3.upload_file(meta_path, meta_s3_key)
            print(f"  [MEDIA] Uploaded video_meta.json (fps={fps:.3f}, duration={duration:.1f}s)")

            # Step 7: Push completion — one transcription task for the full audio
            await rc.push_completed({
                "task_id": task_id,
                "job_id": job_id,
                "type": "media",
                "status": "completed",
                "audio_path": audio_s3_key,
                "video_meta_path": meta_s3_key,
                "duration": duration,
                "fps": fps,
            })

    except Exception as e:
        print(f"  [MEDIA] Failed job {job_id}: {e}")
        await rc.push_completed({
            "task_id": task_id,
            "job_id": job_id,
            "type": "media",
            "status": "failed",
            "error": str(e),
        })
