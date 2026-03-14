"""CalibrationManager のユニットテスト。"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from src.detection.calibration_manager import CalibrationManager
from src.models.calibration_config import CalibrationConfig


def make_simple_config(camera_id: int = 0) -> CalibrationConfig:
    """テスト用キャリブレーション設定を生成する（矩形テーブル想定）。"""
    corners = [(100, 80), (540, 80), (540, 400), (100, 400)]
    src = np.array(corners, dtype=np.float32)
    dst = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)
    import cv2
    H, _ = cv2.findHomography(src, dst)
    return CalibrationConfig(
        camera_id=camera_id,
        table_corners=corners,
        homography_matrix=H,
        created_at="2026-03-14T10:00:00",
    )


class TestCalibrationManagerSaveLoad:
    def test_save_and_load_returns_same_camera_id(self, tmp_path: Path) -> None:
        with patch("src.detection.calibration_manager.CONFIG_DIR", str(tmp_path)):
            manager = CalibrationManager()
            config = make_simple_config(camera_id=0)
            manager.save_config(config)
            loaded = manager.load_config(0)
            assert loaded is not None
            assert loaded.camera_id == 0

    def test_save_and_load_returns_same_corners(self, tmp_path: Path) -> None:
        with patch("src.detection.calibration_manager.CONFIG_DIR", str(tmp_path)):
            manager = CalibrationManager()
            config = make_simple_config(camera_id=0)
            manager.save_config(config)
            loaded = manager.load_config(0)
            assert loaded is not None
            assert loaded.table_corners == config.table_corners

    def test_load_nonexistent_config_returns_none(self, tmp_path: Path) -> None:
        with patch("src.detection.calibration_manager.CONFIG_DIR", str(tmp_path)):
            manager = CalibrationManager()
            result = manager.load_config(99)
            assert result is None

    def test_load_corrupted_json_returns_none(self, tmp_path: Path) -> None:
        with patch("src.detection.calibration_manager.CONFIG_DIR", str(tmp_path)):
            manager = CalibrationManager()
            # 壊れたJSONファイルを作成
            config_path = tmp_path / "calibration_0.json"
            config_path.write_text("{ invalid json }", encoding="utf-8")
            result = manager.load_config(0)
            assert result is None


class TestCalibrationManagerTransformPoint:
    def test_transform_top_left_corner_returns_near_zero(self) -> None:
        """左上頂点の変換結果が (0, 0) に近いこと。"""
        manager = CalibrationManager()
        config = make_simple_config()
        x, y = manager.transform_point(config, px=100, py=80)
        assert x == pytest.approx(0.0, abs=0.01)
        assert y == pytest.approx(0.0, abs=0.01)

    def test_transform_bottom_right_corner_returns_near_one(self) -> None:
        """右下頂点の変換結果が (1, 1) に近いこと。"""
        manager = CalibrationManager()
        config = make_simple_config()
        x, y = manager.transform_point(config, px=540, py=400)
        assert x == pytest.approx(1.0, abs=0.01)
        assert y == pytest.approx(1.0, abs=0.01)

    def test_transform_center_returns_near_half(self) -> None:
        """中心点の変換結果が (0.5, 0.5) に近いこと。"""
        manager = CalibrationManager()
        config = make_simple_config()
        cx = (100 + 540) // 2
        cy = (80 + 400) // 2
        x, y = manager.transform_point(config, px=cx, py=cy)
        assert x == pytest.approx(0.5, abs=0.02)
        assert y == pytest.approx(0.5, abs=0.02)

    def test_transform_with_none_homography_returns_zero(self) -> None:
        """ホモグラフィ行列がNoneの場合は (0, 0) を返すこと。"""
        manager = CalibrationManager()
        config = CalibrationConfig(camera_id=0, table_corners=[], homography_matrix=None)
        x, y = manager.transform_point(config, px=100, py=100)
        assert x == 0.0
        assert y == 0.0
