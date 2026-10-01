"""Regression checks for real upload decoding, retention, privacy boundaries, and preferences."""

import io
import wave
from unittest.mock import patch

import numpy as np
import pytest

from src.apps.web.app import app
from src.shared.history import get_history, get_stats, save_recording
from src.shared.transcriber import transcribe


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    recordings = tmp_path / "recordings"
    uploads = tmp_path / "uploads"
    recordings.mkdir()
    uploads.mkdir()
    for module in ("src.shared.history", "src.apps.web.app", "src.shared.retry_engine"):
        monkeypatch.setattr(f"{module}.RECORDINGS_DIR", recordings)
    monkeypatch.setattr("src.shared.history.HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr("src.shared.settings.SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr("src.apps.web.app.TEMP_UPLOADS_DIR", uploads)
    monkeypatch.setattr("src.shared.personalization.PERSONALIZATION_PATH", tmp_path / "personalization.json")
    monkeypatch.setattr("src.shared.workspace_state.WORKSPACE_PATH", tmp_path / "workspace.json")
    app.config["TESTING"] = True
    return app.test_client(), recordings, uploads


def wav_upload():
    content = io.BytesIO()
    with wave.open(content, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(16000)
        audio = (np.sin(np.arange(16000) * 0.15) * 12000).astype(np.int16)
        file.writeframes(audio.tobytes())
    content.seek(0)
    return content


def test_empty_workspace_reports_zero(workspace):
    assert get_stats()["total_words"] == 0
    assert get_stats()["avg_wpm"] == 0
    assert get_stats()["streak_days"] == 0
    assert "weekly_limit" not in get_stats()


def test_upload_decoded_retained_and_temp_removed(workspace):
    client, recordings, uploads = workspace
    client.post("/api/settings", json={"language": "hi", "model": "small", "llm_enabled": False})
    with (
        patch("src.apps.web.app.transcribe", return_value="a useful little thought") as infer,
        patch("src.apps.web.app.llm_clean") as cleanup,
    ):
        result = client.post("/transcribe", data={"audio": (wav_upload(), "fixture.wav")})
    assert result.status_code == 200
    assert isinstance(infer.call_args.args[0], np.ndarray)
    assert infer.call_args.kwargs["language"] == "hi"
    assert infer.call_args.kwargs["model_name"] == "small"
    cleanup.assert_not_called()
    assert "saved_path" not in result.get_json()
    assert len(list(recordings.glob("*.wav"))) == 1
    assert list(uploads.iterdir()) == []
    entry = get_history()[0]
    assert entry["duration_sec"] == 1
    assert client.get(f"/api/audio/{entry['id']}").status_code == 200
    assert client.delete(f"/api/history/{entry['id']}").get_json()["success"]
    assert list(recordings.iterdir()) == []


def test_temp_removed_on_failed_inference(workspace):
    client, recordings, uploads = workspace
    with patch("src.apps.web.app.transcribe", side_effect=RuntimeError("failure")):
        result = client.post("/transcribe", data={"audio": (wav_upload(), "fixture.wav")})
    assert result.status_code == 500
    assert list(uploads.iterdir()) == []
    assert list(recordings.iterdir()) == []


def test_silence_not_saved(workspace):
    client, recordings, uploads = workspace
    with patch("src.apps.web.app.transcribe", return_value=""):
        result = client.post("/transcribe", data={"audio": (wav_upload(), "fixture.wav")})
    assert result.get_json()["recording_id"] is None
    assert get_history() == []
    assert list(uploads.iterdir()) == []


def test_invalid_settings_rejected_atomically(workspace):
    client, _, _ = workspace
    assert (
        client.post("/api/settings", json={"model": "small", "language": "made-up"}).status_code
        == 400
    )
    assert client.get("/api/settings").get_json()["model"] == "base"
    assert client.post("/api/settings", json={"llm_enabled": "false"}).status_code == 400
    assert client.post("/api/settings", json={"unknown": True}).status_code == 400
    assert (
        client.post("/api/settings", json={"model": "tiny.en", "language": "hi"}).status_code == 400
    )


def test_origin_and_host_restrictions(workspace):
    client, _, _ = workspace
    assert (
        client.post(
            "/api/settings",
            json={"model": "small"},
            headers={"Origin": "https://unrelated.example"},
        ).status_code
        == 403
    )
    assert client.get("/api/history", headers={"Host": "attacker.example"}).status_code == 403
    assert client.get("/api/history", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.get("/api/history", headers={"Host": "[::bad]:5000"}).status_code == 403
    assert (
        client.post(
            "/api/settings", json={"model": "small"}, headers={"Origin": "http://localhost"}
        ).status_code
        == 200
    )


def test_history_limit_validated(workspace):
    client, _, _ = workspace
    for limit in ["abc", "0", "-1", "1001"]:
        assert client.get(f"/api/history?limit={limit}").status_code == 400


def test_dismissed_activity_excluded(workspace):
    save_recording(raw="a useful thought", status="dismissed")
    assert get_stats()["total_words"] == 0
    assert get_stats()["total_recordings"] == 0


def test_file_transcription_decodes_before_inference(workspace):
    with patch(
        "src.shared.transcriber.decode_audio", return_value=np.zeros(16000, dtype=np.float32)
    ) as decode:
        assert transcribe("fixture.wav") == ""
        decode.assert_called_once_with("fixture.wav", sampling_rate=16000)
