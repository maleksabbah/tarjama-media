"""
Media Service Configuration
"""
import os


class Config:
    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Queues
    QUEUE_MEDIA = "queue:media"
    QUEUE_COMPLETED = "queue:completed"

    # Storage paths
    STORAGE_BASE = os.getenv("STORAGE_BASE", "./storage")
    AUDIO_DIR = os.getenv("AUDIO_DIR", "audio")
    CHUNKS_DIR = os.getenv("CHUNKS_DIR", "chunks")

    # Chunking
    CHUNK_DURATION_SECONDS = int(os.getenv("CHUNK_DURATION", "30"))
    SAMPLE_RATE = 16000

    # FFmpeg
    FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
    FFPROBE_PATH = os.getenv("FFPROBE_PATH", "ffprobe")


config = Config()