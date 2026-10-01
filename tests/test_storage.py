"""Exercise shared history writers and one-time legacy identity migration."""

import json
from concurrent.futures import ThreadPoolExecutor

from src.shared.history import get_history, save_recording, update_recording


def test_concurrent_history_writers_do_not_lose_records(tmp_path, monkeypatch):
    monkeypatch.setattr("src.shared.history.HISTORY_PATH", tmp_path / "history.json")
    with ThreadPoolExecutor(max_workers=8) as executor:
        records = list(
            executor.map(lambda i: save_recording(raw=f"fictional thought {i}"), range(30))
        )
    assert len(get_history()) == 30
    assert {record["id"] for record in records} == {record["id"] for record in get_history()}


def test_legacy_identity_survives_reload_and_update(tmp_path, monkeypatch):
    path = tmp_path / "history.json"
    monkeypatch.setattr("src.shared.history.HISTORY_PATH", path)
    path.write_text(json.dumps([{"raw": "a legacy thought"}]))
    first_id = get_history()[0]["id"]
    assert get_history()[0]["id"] == first_id
    assert update_recording(first_id, {"flagged": True})["flagged"] is True
