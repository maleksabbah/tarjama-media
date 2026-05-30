# app/main.py
"""
Media worker entrypoint.
Builds Kafka consumer + producer, S3 client, processing service, worker service,
runs the consumer loop until interrupted.
"""
import asyncio

from app.Config.Config import config
from app.Config.Kafka import get_producer, make_consumer, close_producer
from app.Repositories import EventConsumer, EventPublisher, S3Client
from app.Services import MediaProcessingService, MediaWorkerService


async def main() -> None:
    print("Starting Media Service...")

    producer = await get_producer()
    publisher = EventPublisher(producer)

    consumer = EventConsumer(
        make_consumer(
            topics=[config.TOPIC_MEDIA_TASKS],
            group_id=config.GROUP_MEDIA_WORKER,
        )
    )

    s3 = S3Client()
    processing = MediaProcessingService()

    worker = MediaWorkerService(
        consumer=consumer,
        publisher=publisher,
        s3=s3,
        processing=processing,
    )

    print("Media Service ready.")
    try:
        await worker.run()
    except KeyboardInterrupt:
        pass
    finally:
        await close_producer()
        print("Media Service stopped.")


if __name__ == "__main__":
    asyncio.run(main())