# app/main.py
"""
Media worker entrypoint.
Builds Kafka consumer + producer, S3 client, processing service, worker service,
runs the consumer loop until interrupted.
"""
import asyncio

import httpx

from app.Config.Config import config
from app.Config.Kafka import get_producer, make_consumer, close_producer
from app.Repositories import EventConsumer, EventPublisher, S3Client, StorageClient
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
    http_client = httpx.AsyncClient(timeout=10.0)
    storage = StorageClient(http_client)

    worker = MediaWorkerService(
        consumer=consumer,
        publisher=publisher,
        s3=s3,
        storage=storage,
        processing=processing,
    )

    print("Media Service ready.")
    try:
        await worker.run()
    except KeyboardInterrupt:
        pass
    finally:
        await http_client.aclose()
        await close_producer()
        print("Media Service stopped.")


if __name__ == "__main__":
    asyncio.run(main())