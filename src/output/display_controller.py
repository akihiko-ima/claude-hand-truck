import time
from pathlib import Path

import cv2
import numpy as np

# 清掃完了アラートの表示時間（秒）
ALERT_DURATION_SECONDS = 3.0
# カメラ映像の表示サイズ
CAMERA_DISPLAY_WIDTH = 640
CAMERA_DISPLAY_HEIGHT = 480


class DebugImageSaver:
    """デバッグ用画像の生成・保存を担うクラス。

    カメラ映像・ヒートマップ・清掃完了率を1つの画像に統合し、
    outputs/debug.jpg へ上書き保存する。
    """

    def __init__(self, outputs_dir: Path, total_cells: int = 21) -> None:
        self._outputs_dir = outputs_dir
        self._total_cells = total_cells
        self._alert_shown_at: float | None = None

    def save(
        self,
        frames: dict[int, np.ndarray],
        heatmap: np.ndarray,
        cleaning_rate: float,
    ) -> None:
        """統合画像を outputs/debug.jpg へ上書き保存する。

        レイアウト:
        - 上段: カメラ映像（最大2台を横並び）
        - 中段: ヒートマップ
        - 下段: 清掃完了率テキスト

        Args:
            frames: カメラIDをキー、フレームを値とした辞書
            heatmap: ヒートマップ画像（ndarray）
            cleaning_rate: 清掃完了率 (0.0〜1.0)
        """
        camera_panels = []
        for cam_id in sorted(frames.keys()):
            resized = cv2.resize(
                frames[cam_id],
                (CAMERA_DISPLAY_WIDTH, CAMERA_DISPLAY_HEIGHT),
            )
            camera_panels.append(resized)

        if not camera_panels:
            placeholder = np.zeros(
                (CAMERA_DISPLAY_HEIGHT, CAMERA_DISPLAY_WIDTH, 3), dtype=np.uint8
            )
            cv2.putText(
                placeholder, "No Camera", (200, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 100), 2,
            )
            camera_panels = [placeholder]

        camera_row = np.hstack(camera_panels)
        total_width = camera_row.shape[1]

        heatmap_resized = cv2.resize(heatmap, (total_width, heatmap.shape[0]))

        status_bar = self._create_status_bar(total_width, cleaning_rate)

        combined = np.vstack([camera_row, heatmap_resized, status_bar])

        if cleaning_rate >= 1.0:
            if self._alert_shown_at is None:
                self._alert_shown_at = time.time()
            elapsed = time.time() - self._alert_shown_at
            if elapsed <= ALERT_DURATION_SECONDS:
                combined = self._draw_alert(combined)
        else:
            self._alert_shown_at = None

        cv2.imwrite(str(self._outputs_dir / "debug.jpg"), combined)

    def _create_status_bar(self, width: int, cleaning_rate: float) -> np.ndarray:
        """清掃完了率を表示するステータスバーを生成する。"""
        bar = np.zeros((50, width, 3), dtype=np.uint8)
        cleaned_cells = round(cleaning_rate * self._total_cells)
        text = f"Cleaning: {cleaned_cells}/{self._total_cells} ({cleaning_rate * 100:.1f}%)"
        cv2.putText(
            bar, text, (10, 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2,
        )
        return bar

    def _draw_alert(self, img: np.ndarray) -> np.ndarray:
        """清掃完了アラートを半透明オーバーレイで描画する。"""
        overlay = img.copy()
        h, w = img.shape[:2]

        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        result = cv2.addWeighted(overlay, 0.4, img, 0.6, 0)

        text = "ALL CLEAN!"
        font_scale = 3.0
        thickness = 4
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
        text_x = (w - text_size[0]) // 2
        text_y = (h + text_size[1]) // 2
        cv2.putText(
            result, text, (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 255, 0), thickness,
        )
        return result
