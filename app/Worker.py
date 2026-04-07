"""
Media Worker (S3 version)
Pop task → download video from S3 → extract audio → chunk → upload chunks to S3 → push completion.
"""
import os
import tempfile
from app.Config import config
from app import Redis_client as rc
from app import S3_client as s3
from app.Extractor import extract_audio, get_duration
from app.Chunker import detect_silence, find_split_points, split_audio


async def process_task(message: dict):
    task_id = message["task_id"]
    job_id = message["job_id"]
    input_s3_key = message["input_path"]  # e.g., "uploads/j_123/video.mp4"

    print(f"  [MEDIA] Processing job {job_id}: {input_s3_key}")

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Step 1: Download video from S3 to temp
            local_video = os.path.join(tmp_dir, "video.mp4")
            print(f"  [MEDIA] Downloading video from S3...")
            s3.download_file(input_s3_key, local_video)

            # Step 2: Extract audio → 16kHz mono WAV
            local_audio = os.path.join(tmp_dir, "full_audio.wav")
            print(f"  [MEDIA] Extracting audio...")
            extract_audio(local_video, local_audio)

            # Step 3: Get duration
            duration = get_duration(local_audio)
            print(f"  [MEDIA] Duration: {duration:.1f}s")

            # Step 4: Upload full audio to S3
            audio_s3_key = f"audio/{job_id}/full_audio.wav"
            s3.upload_file(local_audio, audio_s3_key)

            # Step 5: Detect silence and find split points
            print(f"  [MEDIA] Detecting silence...")
            silence_points = detect_silence(local_audio)
            split_points = find_split_points(duration, silence_points)

            # Step 6: Split audio into chunks
            chunks_dir = os.path.join(tmp_dir, "chunks")
            print(f"  [MEDIA] Splitting into chunks...")
            local_chunks = split_audio(local_audio, chunks_dir, job_id,
                                       split_points=split_points, duration=duration)

            # Step 7: Upload each chunk to S3
            chunk_s3_keys = []
            for i, local_chunk in enumerate(local_chunks):
                chunk_key = f"chunks/{job_id}/chunk_{i:04d}.wav"
                s3.upload_file(local_chunk, chunk_key)
                chunk_s3_keys.append(chunk_key)

            print(f"  [MEDIA] Uploaded {len(chunk_s3_keys)} chunks to S3")

            # Step 8: Push completion
            await rc.push_completed({
                "task_id": task_id,
                "job_id": job_id,
                "type": "media",
                "status": "completed",
                "chunks": chunk_s3_keys,
                "total_chunks": len(chunk_s3_keys),
                "duration": duration,
                "audio_path": audio_s3_key,
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