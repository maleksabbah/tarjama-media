"""
ASR Media Service
==================
Extracts audio from video, splits into chunks for parallel transcription.
Runs as a background worker — no HTTP server.

Run:
  python -m app.main
"""
import asyncio
from app.Config import config
from app import Redis_client as rc
from app.Worker import process_task


async def main():
    """Main worker loop."""
    print("Starting Media Service...")
    await rc.init_redis()
    print("  Redis connected")
    print("Media Service ready. Waiting for tasks...")

    try:
        while True:
            try:
                message = await rc.pop_media_task(timeout=5)
                if message:
                    print(f"  [MEDIA] Received task for job {message.get('job_id')}")
                    await process_task(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"  [MEDIA] Error: {e}")
                await asyncio.sleep(1)
    finally:
        print("Shutting down Media Service...")
        await rc.close_redis()
        print("Media Service stopped.")


if __name__ == "__main__":
    asyncio.run(main())