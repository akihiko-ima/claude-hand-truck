import json
import logging
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from src.models.calibration_config import CalibrationConfig

logger = logging.getLogger(__name__)

CONFIG_DIR = "config"
_WINDOW_NAME_PREFIX = "Calibration - Camera"


class CalibrationManager:
    """カメラキャリブレーション設定の管理クラス。

    マウス操作でテーブルの4頂点を指定し、ホモグラフィ行列を算出する。
    設定は config/calibration_{camera_id}.json に保存・読み込みする。
    """

    def __init__(self) -> None:
        Path(CONFIG_DIR).mkdir(parents=True, exist_ok=True)
        self._clicked_points: list[tuple[int, int]] = []

    def run_calibration(self, camera_id: int, frame: np.ndarray) -> CalibrationConfig:
        """インタラクティブなキャリブレーションUIを起動し、設定を返す。

        表示されたカメラ映像上で4頂点をクリックする（左上→右上→右下→左下の時計回り）。
        4点クリック後に自動的にホモグラフィ行列を計算して設定を返す。

        Args:
            camera_id: キャリブレーション対象のカメラID
            frame: キャリブレーション用のカメラフレーム

        Returns:
            算出した CalibrationConfig
        """
        self._clicked_points = []
        window_name = f"{_WINDOW_NAME_PREFIX} {camera_id}"
        display_frame = frame.copy()

        cv2.namedWindow(window_name)
        cv2.setMouseCallback(
            window_name,
            self._mouse_callback,
            {"frame": display_frame, "window_name": window_name},
        )

        print(f"カメラ{camera_id}のキャリブレーション開始。")
        print("テーブルの4頂点を時計回りにクリックしてください（左上→右上→右下→左下）。")

        while True:
            show_frame = display_frame.copy()
            # クリック済みの点を表示
            for i, pt in enumerate(self._clicked_points):
                cv2.circle(show_frame, pt, 6, (0, 255, 0), -1)
                cv2.putText(
                    show_frame, str(i + 1), (pt[0] + 8, pt[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
                )
            # 点をつないで多角形表示
            if len(self._clicked_points) >= 2:
                pts = np.array(self._clicked_points, dtype=np.int32)
                cv2.polylines(show_frame, [pts], False, (0, 255, 0), 2)

            remaining = 4 - len(self._clicked_points)
            msg = f"Click {remaining} more point(s)" if remaining > 0 else "Done! (4/4)"
            cv2.putText(
                show_frame, msg, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2,
            )
            cv2.imshow(window_name, show_frame)

            if len(self._clicked_points) == 4:
                break

            key = cv2.waitKey(30) & 0xFF
            # r キーでリセット
            if key == ord("r"):
                self._clicked_points = []
                display_frame = frame.copy()
                print("クリックをリセットしました。再度4頂点をクリックしてください。")

        cv2.destroyWindow(window_name)

        config = self._build_config(camera_id, self._clicked_points)
        self.save_config(config)
        print(f"カメラ{camera_id}のキャリブレーション設定を保存しました。")
        return config

    def _mouse_callback(
        self,
        event: int,
        x: int,
        y: int,
        flags: int,
        param: dict,  # type: ignore[type-arg]
    ) -> None:
        """マウスクリックで頂点を記録するコールバック。"""
        if event == cv2.EVENT_LBUTTONDOWN and len(self._clicked_points) < 4:
            self._clicked_points.append((x, y))

    def _build_config(
        self, camera_id: int, corners: list[tuple[int, int]]
    ) -> CalibrationConfig:
        """4頂点からホモグラフィ行列を計算してキャリブレーション設定を生成する。"""
        # テーブル正規化座標の目標点（左上→右上→右下→左下）
        dst_points = np.array(
            [[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32
        )
        src_points = np.array(corners, dtype=np.float32)
        homography_matrix, _ = cv2.findHomography(src_points, dst_points)

        return CalibrationConfig(
            camera_id=camera_id,
            table_corners=corners,
            homography_matrix=homography_matrix,
            created_at=datetime.now().isoformat(),
        )

    def save_config(self, config: CalibrationConfig) -> None:
        """キャリブレーション設定をJSONファイルに保存する。"""
        config_path = Path(CONFIG_DIR) / f"calibration_{config.camera_id}.json"
        data = {
            "camera_id": config.camera_id,
            "table_corners": config.table_corners,
            "homography_matrix": (
                config.homography_matrix.tolist()
                if config.homography_matrix is not None
                else None
            ),
            "created_at": config.created_at,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_config(self, camera_id: int) -> CalibrationConfig | None:
        """保存済みのキャリブレーション設定を読み込む。

        Args:
            camera_id: 読み込み対象のカメラID

        Returns:
            読み込んだ CalibrationConfig、存在しない・破損の場合は None
        """
        config_path = Path(CONFIG_DIR) / f"calibration_{camera_id}.json"
        if not config_path.exists():
            return None

        try:
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)

            homography_matrix = (
                np.array(data["homography_matrix"], dtype=np.float64)
                if data.get("homography_matrix") is not None
                else None
            )
            return CalibrationConfig(
                camera_id=data["camera_id"],
                table_corners=[tuple(pt) for pt in data["table_corners"]],
                homography_matrix=homography_matrix,
                created_at=data.get("created_at", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"設定ファイルが破損しています。再設定が必要です。({e})")
            return None

    def transform_point(
        self, config: CalibrationConfig, px: int, py: int
    ) -> tuple[float, float]:
        """カメラ画素座標をテーブル正規化座標（0-1）に変換する。

        Args:
            config: キャリブレーション設定
            px: カメラ画像上のX座標（ピクセル）
            py: カメラ画像上のY座標（ピクセル）

        Returns:
            テーブル正規化座標 (x_normalized, y_normalized)
        """
        if config.homography_matrix is None:
            return 0.0, 0.0

        src = np.array([[[px, py]]], dtype=np.float32)
        dst = cv2.perspectiveTransform(src, config.homography_matrix)
        x_norm = float(dst[0][0][0])
        y_norm = float(dst[0][0][1])
        return x_norm, y_norm
