# app/Config/Config.py
"""
Media worker config — environment variables.
"""
import os


class Config:
    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

    # Topics
    TOPIC_MEDIA_TASKS: str = os.getenv("TOPIC_MEDIA_TASKS", "tarjama.media.tasks")
    TOPIC_COMPLETED: str = os.getenv("TOPIC_COMPLETED", "tarjama.completed")

    # Consumer group
    GROUP_MEDIA_WORKER: str = os.getenv("GROUP_MEDIA_WORKER", "tarjama.media")

    # ffmpeg
    FFMPEG_PATH: str = os.getenv("FFMPEG_PATH", "ffmpeg")
    FFPROBE_PATH: str = os.getenv("FFPROBE_PATH", "ffprobe")

    # Audio output format
    SAMPLE_RATE: int = int(os.getenv("SAMPLE_RATE", "16000"))
    # media: app/Config/Config.py — add this line in the Config class
    STORAGE_URL: str = os.getenv("STORAGE_URL", "http://storage:8002")


config = Config()