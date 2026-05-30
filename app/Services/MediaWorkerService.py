# media: app/Services/MediaWorkerService.py
"""
Media worker orchestrator.
Pulls messages off the Kafka consumer, processes each (download → extract →
upload → register → publish completion), commits the offset on success.
"""
import os
import json
import tempfile

from app.Repositories import EventConsumer, EventPublisher, S3Client, StorageClient
from app.Services.MediaProcessingService import MediaProcessingService


class MediaWorkerService:
    def __init__(
        self,
        consumer: EventConsumer,
        publisher: EventPublisher,
        s3: S3Client,
        storage: StorageClient,
        processing: MediaProcessingService,
    ):
        self.consumer = consumer
        self.publisher = publisher
        self.s3 = s3
        self.storage = storage
        self.processing = processing

    async def run(self) -> None:
        await self.consumer.start()
        print("  [MEDIA] Consumer started")
        try:
            async for message in self.consumer.messages():
                try:
                    await self.process(message)
                    await self.consumer.commit()
                except Exception as e:
                    print(f"  [MEDIA] Handler error, will redeliver: {e}")
        finally:
            await self.consumer.stop()
            print("  [MEDIA] Consumer stopped")

    async def process(self, message: dict) -> None:
        task_id = message["task_id"]
        job_id = message["job_id"]
        user_id = message.get("user_id", 0)
        input_s3_key = message["input_path"]

        print(f"  [MEDIA] Processing job {job_id}: {input_s3_key}")

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                # 1. Download video
                local_video = os.path.join(tmp_dir, "video.mp4")
                self.s3.download_file(input_s3_key, local_video)

                # 2. FPS
                fps = self.processing.get_video_fps(local_video)
                print(f"  [MEDIA] FPS: {fps:.3f}")

                # 3. Extract audio
                local_audio = os.path.join(tmp_dir, "audio.wav")
                self.processing.extract_audio(local_video, local_audio)

                # 4. Duration
                duration = self.processing.get_duration(local_audio)
                print(f"  [MEDIA] Duration: {duration:.1f}s")

                # 5. Upload audio
                audio_s3_key = f"audio/{job_id}/full_audio.wav"
                self.s3.upload_file(local_audio, audio_s3_key)
                await self.storage.register_file(
                    job_id=job_id,
                    user_id=user_id,
                    category="audio",
                    file_type="wav",
                    path=audio_s3_key,
                    mime_type="audio/wav",
                )

                # 6. Upload meta
                meta = {"fps": fps, "duration": duration, "job_id": job_id}
                meta_s3_key = f"audio/{job_id}/video_meta.json"
                self.s3.upload_json_string(json.dumps(meta, indent=2), meta_s3_key)
                await self.storage.register_file(
                    job_id=job_id,
                    user_id=user_id,
                    category="meta",
                    file_type="json",
                    path=meta_s3_key,
                    mime_type="application/json",
                )

                # 7. Publish completion
                await self.publisher.publish_completion({
                    "task_id": task_id,
                    "job_id": job_id,
                    "type": "media",
                    "status": "completed",
                    "audio_path": audio_s3_key,
                    "video_meta_path": meta_s3_key,
                    "duration": duration,
                    "fps": fps,
                })
                print(f"  [MEDIA] Done: {job_id}")

        except Exception as e:
            print(f"  [MEDIA] Failed {job_id}: {e}")
            await self.publisher.publish_completion({
                "task_id": task_id,
                "job_id": job_id,
                "type": "media",
                "status": "failed",
                "error": str(e),
            })


