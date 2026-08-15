from unittest.mock import patch

import numpy as np
import pytest

from config import SAMPLE_RATE
from src.apps.web.app import app
from src.shared.history import (
    delete_recording,
    dismiss_recording,
    get_history,
    get_recording,
    get_stats,
    recover_recording,
    save_recording,
)
from src.shared.retry_engine import retranscribe_recording, retry_cleanup


@pytest.fixture
def mock_history_env(tmp_path, monkeypatch):
    """Isolate history storage and recordings in temporary directory."""
    hist_file = tmp_path / "test_history.json"
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("src.shared.history.HISTORY_PATH", hist_file)
    monkeypatch.setattr("src.shared.history.RECORDINGS_DIR", rec_dir)
    monkeypatch.setattr("src.shared.retry_engine.RECORDINGS_DIR", rec_dir)
    monkeypatch.setattr("src.apps.web.app.RECORDINGS_DIR", rec_dir)

    return {"hist_file": hist_file, "rec_dir": rec_dir}


class TestAudioRecordingsPersistence:
    def test_save_recording_with_audio_array(self, mock_history_env):
        # 1 second of 440Hz sine wave
        t = np.linspace(0, 1, SAMPLE_RATE, dtype=np.float32)
        audio = 0.5 * np.sin(2 * np.pi * 440 * t)

        entry = save_recording(
            audio=audio,
            raw="hello world test",
            cleaned="Hello world test.",
            formatted="Hello world test.",
            app="Slack",
            latency_ms=45,
            model_used="base",
            llm_model="qwen2.5-0.5b",
        )

        assert entry["id"].startswith("rec_")
        assert entry["app"] == "Slack"
        assert entry["word_count"] == 3
        assert entry["audio_file"] is not None
        assert entry["status"] == "completed"

        # Verify WAV file exists on disk
        wav_path = mock_history_env["rec_dir"] / entry["audio_file"]
        assert wav_path.exists()
        assert wav_path.stat().st_size > 1000

    def test_history_query_and_search(self, mock_history_env):
        save_recording(raw="Discuss quarterly roadmap", app="Slack")
        save_recording(raw="Fix bug in auth service", app="Cursor")

        all_items = get_history()
        assert len(all_items) == 2

        # Search query matching
        search_auth = get_history(search_query="auth")
        assert len(search_auth) == 1
        assert "auth" in search_auth[0]["raw"].lower()

        search_slack = get_history(search_query="slack")
        assert len(search_slack) == 1

    def test_dismiss_and_recover(self, mock_history_env):
        rec = save_recording(raw="Accidental background chatter", app="General")
        rec_id = rec["id"]

        assert dismiss_recording(rec_id) is True
        updated = get_recording(rec_id)
        assert updated["status"] == "dismissed"

        assert recover_recording(rec_id) is True
        recovered = get_recording(rec_id)
        assert recovered["status"] == "completed"

    def test_delete_recording_removes_file(self, mock_history_env):
        audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
        rec = save_recording(audio=audio, raw="Temporary voice draft")
        rec_id = rec["id"]
        wav_path = mock_history_env["rec_dir"] / rec["audio_file"]
        assert wav_path.exists()

        assert delete_recording(rec_id) is True
        assert get_recording(rec_id) is None
        assert not wav_path.exists()

    def test_get_stats_calculation(self, mock_history_env):
        save_recording(raw="One two three four five", duration_sec=2.0)
        save_recording(raw="Six seven eight nine ten", duration_sec=2.0)

        stats = get_stats()
        assert stats["total_words"] == 10
        assert stats["total_recordings"] == 2
        assert "avg_wpm" in stats


class TestRetryEngine:
    @patch("src.shared.retry_engine.clean")
    def test_retry_cleanup(self, mock_clean, mock_history_env):
        mock_clean.return_value = ("Cleaned up response text.", 55)
        rec = save_recording(raw="um so i wanted to reply")

        updated = retry_cleanup(rec["id"], transform_style="clean")
        assert updated["cleaned"] == "Cleaned up response text."
        assert updated["status"] == "completed"

    @patch("src.shared.retry_engine.transcribe")
    @patch("src.shared.retry_engine.clean")
    def test_retranscribe_recording(self, mock_clean, mock_transcribe, mock_history_env):
        audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
        rec = save_recording(audio=audio, raw="Initial draft")

        mock_transcribe.return_value = "Retranscribed high precision text"
        mock_clean.return_value = ("Retranscribed high precision text.", 60)

        updated = retranscribe_recording(
            rec["id"],
            model_name="small",
            language="en",
        )

        assert updated["raw"] == "Retranscribed high precision text"
        assert updated["model_used"] == "small"


class TestFlowDashboardAPI:
    @pytest.fixture
    def client(self, mock_history_env):
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_get_history_api(self, client, mock_history_env):
        save_recording(raw="Test API recording 1")
        save_recording(raw="Test API recording 2")

        res = client.get("/api/history")
        assert res.status_code == 200
        data = res.get_json()
        assert data["count"] == 2
        assert len(data["recordings"]) == 2

    def test_audio_streaming_endpoint(self, client, mock_history_env):
        audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
        rec = save_recording(audio=audio, raw="Audio stream test")

        res = client.get(f"/api/audio/{rec['id']}")
        assert res.status_code == 200
        assert res.content_type == "audio/wav"

    def test_stats_endpoint(self, client, mock_history_env):
        res = client.get("/api/stats")
        assert res.status_code == 200
        data = res.get_json()
        assert "total_words" in data
        assert "avg_wpm" in data
        assert "streak_days" in data

    @patch("src.apps.web.app.retry_cleanup")
    def test_retry_cleanup_endpoint(self, mock_retry, client, mock_history_env):
        rec = save_recording(raw="Retry route test")
        mock_retry.return_value = {"id": rec["id"], "formatted": "Cleaned route result."}

        res = client.post(f"/api/retry_cleanup/{rec['id']}", json={"style": "clean"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["recording"]["formatted"] == "Cleaned route result."

    def test_dismiss_and_recover_endpoints(self, client, mock_history_env):
        rec = save_recording(raw="Dismiss API test")
        rec_id = rec["id"]

        res = client.post(f"/api/history/{rec_id}/dismiss")
        assert res.status_code == 200
        assert get_recording(rec_id)["status"] == "dismissed"

        res = client.post(f"/api/history/{rec_id}/recover")
        assert res.status_code == 200
        assert get_recording(rec_id)["status"] == "completed"
