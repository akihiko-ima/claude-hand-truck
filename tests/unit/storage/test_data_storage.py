"""DataStorage のユニットテスト。"""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from src.models.cleaning_session import CleaningSession
from src.models.grid_cell import GridCell
from src.storage.data_storage import DataStorage


def make_session(session_id: str = "20260314_100000") -> CleaningSession:
    """テスト用清掃セッションを生成するヘルパー。"""
    grid_cells = [
        [GridCell(row=r, col=c) for c in range(12)]
        for r in range(2)
    ]
    grid_cells[0][0].accumulated_seconds = 7.2
    grid_cells[0][0].is_cleaned = True
    return CleaningSession(
        session_id=session_id,
        table_id="table_01",
        started_at="2026-03-14T10:00:00",
        grid_cells=grid_cells,
        cleaning_rate=1 / 24,
    )


class TestDataStorageCreateSession:
    def test_create_session_returns_valid_session(self, tmp_path: Path) -> None:
        with patch("src.storage.data_storage.DataStorage.BASE_DIR", str(tmp_path)):
            storage = DataStorage()
            session = storage.create_session("table_01")
            assert session.table_id == "table_01"
            assert session.ended_at is None
            assert len(session.grid_cells) == 2
            assert all(len(row) == 12 for row in session.grid_cells)

    def test_create_session_creates_directory(self, tmp_path: Path) -> None:
        with patch("src.storage.data_storage.DataStorage.BASE_DIR", str(tmp_path)):
            storage = DataStorage()
            session = storage.create_session("table_01")
            session_dir = tmp_path / session.session_id
            assert session_dir.exists()


class TestDataStorageSaveSession:
    def test_save_session_creates_json_file(self, tmp_path: Path) -> None:
        with patch("src.storage.data_storage.DataStorage.BASE_DIR", str(tmp_path)):
            storage = DataStorage()
            session = make_session()
            heatmap = np.zeros((240, 960, 3), dtype=np.uint8)
            storage.save_session(session, heatmap)
            json_path = tmp_path / session.session_id / "session.json"
            assert json_path.exists()

    def test_save_session_json_has_correct_session_id(self, tmp_path: Path) -> None:
        with patch("src.storage.data_storage.DataStorage.BASE_DIR", str(tmp_path)):
            storage = DataStorage()
            session = make_session("20260314_120000")
            heatmap = np.zeros((240, 960, 3), dtype=np.uint8)
            storage.save_session(session, heatmap)
            json_path = tmp_path / "20260314_120000" / "session.json"
            data = json.loads(json_path.read_text(encoding="utf-8"))
            assert data["session_id"] == "20260314_120000"

    def test_save_session_json_has_correct_cleaning_rate(self, tmp_path: Path) -> None:
        with patch("src.storage.data_storage.DataStorage.BASE_DIR", str(tmp_path)):
            storage = DataStorage()
            session = make_session()
            session.cleaning_rate = 0.5
            heatmap = np.zeros((240, 960, 3), dtype=np.uint8)
            storage.save_session(session, heatmap)
            json_path = tmp_path / session.session_id / "session.json"
            data = json.loads(json_path.read_text(encoding="utf-8"))
            assert data["cleaning_rate"] == pytest.approx(0.5)


class TestDataStorageLoadSession:
    def test_load_session_returns_none_for_nonexistent(self, tmp_path: Path) -> None:
        with patch("src.storage.data_storage.DataStorage.BASE_DIR", str(tmp_path)):
            storage = DataStorage()
            result = storage.load_session("nonexistent_session")
            assert result is None

    def test_save_and_load_preserves_grid_cells(self, tmp_path: Path) -> None:
        with patch("src.storage.data_storage.DataStorage.BASE_DIR", str(tmp_path)):
            storage = DataStorage()
            session = make_session("20260314_100000")
            heatmap = np.zeros((240, 960, 3), dtype=np.uint8)
            storage.save_session(session, heatmap)

            loaded = storage.load_session("20260314_100000")
            assert loaded is not None
            assert loaded.grid_cells[0][0].accumulated_seconds == pytest.approx(7.2)
            assert loaded.grid_cells[0][0].is_cleaned is True

    def test_save_and_load_preserves_table_id(self, tmp_path: Path) -> None:
        with patch("src.storage.data_storage.DataStorage.BASE_DIR", str(tmp_path)):
            storage = DataStorage()
            session = make_session()
            heatmap = np.zeros((240, 960, 3), dtype=np.uint8)
            storage.save_session(session, heatmap)

            loaded = storage.load_session(session.session_id)
            assert loaded is not None
            assert loaded.table_id == "table_01"

    def test_load_corrupted_json_returns_none(self, tmp_path: Path) -> None:
        with patch("src.storage.data_storage.DataStorage.BASE_DIR", str(tmp_path)):
            storage = DataStorage()
            session_dir = tmp_path / "bad_session"
            session_dir.mkdir()
            (session_dir / "session.json").write_text("not json", encoding="utf-8")
            result = storage.load_session("bad_session")
            assert result is None
