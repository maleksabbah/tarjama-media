"""
Media Service Unit Tests
Run: pytest Tests.py -v
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

# Explicit imports so patch() can find the modules
import app.Extractor
import app.Chunker
import app.Worker
import app.Redis_client


class TestGetDuration:
    def test_parses_ffprobe_output(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"format": {"duration": "125.430000"}})
        with patch("subprocess.run", return_value=mock_result):
            from app.Extractor import get_duration
            assert get_duration("test.mp4") == 125.43

    def test_raises_on_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "No such file"
        with patch("subprocess.run", return_value=mock_result):
            from app.Extractor import get_duration
            with pytest.raises(RuntimeError, match="ffprobe failed"):
                get_duration("nonexistent.mp4")


class TestExtractAudio:
    def test_calls_ffmpeg_and_returns_path(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result), patch("os.makedirs"):
            from app.Extractor import extract_audio
            assert extract_audio("input.mp4", "output/audio.wav") == "output/audio.wav"

    def test_raises_on_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Invalid input"
        with patch("subprocess.run", return_value=mock_result), patch("os.makedirs"):
            from app.Extractor import extract_audio
            with pytest.raises(RuntimeError, match="FFmpeg audio extraction failed"):
                extract_audio("bad.mp4", "output/audio.wav")


class TestDetectSilence:
    def test_parses_silence_points(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = (
            "[silencedetect @ 0x1234] silence_end: 28.500 | silence_duration: 0.8\n"
            "[silencedetect @ 0x1234] silence_end: 55.200 | silence_duration: 1.2\n"
            "[silencedetect @ 0x1234] silence_end: 82.100 | silence_duration: 0.6\n"
        )
        with patch("subprocess.run", return_value=mock_result):
            from app.Chunker import detect_silence
            points = detect_silence("audio.wav")
            assert len(points) == 3
            assert points[0] == 28.5

    def test_returns_empty_on_no_silence(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = "some output with no silence_end"
        with patch("subprocess.run", return_value=mock_result):
            from app.Chunker import detect_silence
            assert detect_silence("audio.wav") == []


class TestFindSplitPoints:
    def test_splits_near_silence(self):
        from app.Chunker import find_split_points
        points = find_split_points(150.0, [28.5, 55.2, 82.1, 110.0, 138.0], target_duration=30)
        assert len(points) > 0

    def test_no_splits_for_short_audio(self):
        from app.Chunker import find_split_points
        assert find_split_points(20.0, [10.0], target_duration=30) == []

    def test_falls_back_when_no_silence(self):
        from app.Chunker import find_split_points
        assert len(find_split_points(100.0, [], target_duration=30)) > 0


class TestSplitAudio:
    def test_creates_chunks(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result), \
             patch("os.makedirs"), \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=5000):
            from app.Chunker import split_audio
            assert len(split_audio("audio.wav", "output/", "j_123", split_points=[30.0, 60.0], duration=90.0)) == 3

    def test_skips_empty_chunks(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result), \
             patch("os.makedirs"), \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=500):
            from app.Chunker import split_audio
            assert len(split_audio("audio.wav", "output/", "j_123", split_points=[30.0], duration=60.0)) == 0


@pytest.mark.asyncio
class TestMediaWorker:
    async def test_successful_processing(self):
        mock_push = AsyncMock()
        with patch("app.Worker.extract_audio", return_value="audio/j_123/full_audio.wav"), \
             patch("app.Worker.get_duration", return_value=120.0), \
             patch("app.Worker.detect_silence", return_value=[28.0, 55.0, 82.0]), \
             patch("app.Worker.find_split_points", return_value=[28.0, 55.0, 82.0]), \
             patch("app.Worker.split_audio", return_value=["c0.wav", "c1.wav", "c2.wav", "c3.wav"]), \
             patch("app.Worker.rc.push_completed", mock_push):
            from app.Worker import process_task
            await process_task({"task_id": "t_001", "job_id": "j_123", "input_path": "video.mp4"})
            call_args = mock_push.call_args[0][0]
            assert call_args["status"] == "completed"
            assert call_args["total_chunks"] == 4

    async def test_failure_pushes_error(self):
        mock_push = AsyncMock()
        with patch("app.Worker.extract_audio", side_effect=RuntimeError("FFmpeg crashed")), \
             patch("app.Worker.rc.push_completed", mock_push):
            from app.Worker import process_task
            await process_task({"task_id": "t_001", "job_id": "j_123", "input_path": "video.mp4"})
            call_args = mock_push.call_args[0][0]
            assert call_args["status"] == "failed"
            assert "FFmpeg crashed" in call_args["error"]


@pytest.mark.asyncio
class TestRedisClient:
    async def test_pop_media_task(self):
        mock_client = AsyncMock()
        mock_client.brpop.return_value = ("queue:media", json.dumps({"task_id": "t_001", "job_id": "j_123"}))
        with patch("app.Redis_client.client", mock_client):
            from app.Redis_client import pop_media_task
            result = await pop_media_task()
            assert result["task_id"] == "t_001"

    async def test_pop_returns_none_on_timeout(self):
        mock_client = AsyncMock()
        mock_client.brpop.return_value = None
        with patch("app.Redis_client.client", mock_client):
            from app.Redis_client import pop_media_task
            assert await pop_media_task() is None

    async def test_push_completed(self):
        mock_client = AsyncMock()
        with patch("app.Redis_client.client", mock_client):
            from app.Redis_client import push_completed
            await push_completed({"task_id": "t_001", "status": "completed"})
            mock_client.lpush.assert_called_once()