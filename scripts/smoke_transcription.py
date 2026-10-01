"""Optional real-model smoke check with caller-supplied fictional speech audio."""

import argparse
import io
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.apps.web.app import app  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model", default="base")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rma-model-smoke-") as temporary:
        directory = Path(temporary)
        recordings = directory / "recordings"
        uploads = directory / "uploads"
        recordings.mkdir()
        uploads.mkdir()
        with (
            patch("src.shared.history.HISTORY_PATH", directory / "history.json"),
            patch("src.shared.history.RECORDINGS_DIR", recordings),
            patch("src.apps.web.app.RECORDINGS_DIR", recordings),
            patch("src.apps.web.app.TEMP_UPLOADS_DIR", uploads),
            patch("src.shared.settings.SETTINGS_PATH", directory / "settings.json"),
            patch("src.shared.dictionary.DICTIONARY_PATH", directory / "dictionary.json"),
            patch("src.shared.personalization.PERSONALIZATION_PATH", directory / "personalization.json"),
            patch("src.shared.workspace_state.WORKSPACE_PATH", directory / "workspace.json"),
        ):
            client = app.test_client()
            assert (
                client.post(
                    "/api/settings",
                    json={"model": args.model, "language": "en", "llm_enabled": False},
                ).status_code
                == 200
            )
            result = client.post(
                "/transcribe",
                data={"audio": (io.BytesIO(args.audio.read_bytes()), args.audio.name)},
            )
            assert result.status_code == 200, result.get_json()
            payload = result.get_json()
            assert payload["text"].strip(), "No speech detected"
            history = client.get("/api/history").get_json()["recordings"]
            assert len(history) == 1 and history[0]["audio_file"]
            recording_id = history[0]["id"]
            assert client.get(f"/api/audio/{recording_id}").status_code == 200
            assert client.delete(f"/api/history/{recording_id}").get_json()["success"]
            assert not list(recordings.iterdir()) and not list(uploads.iterdir())
            print(
                f"Real-model smoke passed: {args.model}, {len(payload['text'].split())} recognized words; upload/decode/inference/save/playback/delete, isolated fixture storage. Does not validate human microphone accuracy."
            )


if __name__ == "__main__":
    main()
