import time

import cv2
import numpy as np

# 清掃完了アラートの表示時間（秒）
ALERT_DURATION_SECONDS = 3.0
# カメラ映像の表示サイズ
CAMERA_DISPLAY_WIDTH = 640
CAMERA_DISPLAY_HEIGHT = 480


class DisplayController:
    """統合画面の表示を担うクラス。

    カメラ映像・ヒートマップ・清掃完了率を1つのウィンドウに統合表示する。
    全セル清掃完了時に3秒間のアラートを表示する。
    """

    def __init__(self, window_name: str = "CleanTrack") -> None:
        self._window_name = window_name
        self._alert_shown_at: float | None = None
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    def show(
        self,
        frames: dict[int, np.ndarray],
        heatmap: np.ndarray,
        cleaning_rate: float,
    ) -> None:
        """統合画面を表示する。

        レイアウト:
        - 上段: カメラ映像（最大2台を横並び）
        - 中段: ヒートマップ
        - 下段: 清掃完了率テキスト

        Args:
            frames: カメラIDをキー、フレームを値とした辞書
            heatmap: ヒートマップ画像（ndarray）
            cleaning_rate: 清掃完了率 (0.0〜1.0)
        """
        # カメラ映像を同じサイズにリサイズして横並び
        camera_panels = []
        for cam_id in sorted(frames.keys()):
            resized = cv2.resize(
                frames[cam_id],
                (CAMERA_DISPLAY_WIDTH, CAMERA_DISPLAY_HEIGHT),
            )
            camera_panels.append(resized)

        # カメラが0台の場合はプレースホルダーを表示
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

        # ヒートマップを画面幅に合わせてリサイズ
        heatmap_resized = cv2.resize(heatmap, (total_width, heatmap.shape[0]))

        # ステータスバー（清掃完了率）
        status_bar = self._create_status_bar(total_width, cleaning_rate)

        # 統合画像の組み立て
        combined = np.vstack([camera_row, heatmap_resized, status_bar])

        # 清掃完了アラートのオーバーレイ
        if cleaning_rate >= 1.0:
            if self._alert_shown_at is None:
                self._alert_shown_at = time.time()
            elapsed = time.time() - self._alert_shown_at
            if elapsed <= ALERT_DURATION_SECONDS:
                combined = self._draw_alert(combined)
        else:
            self._alert_shown_at = None

        cv2.imshow(self._window_name, combined)

    def _create_status_bar(self, width: int, cleaning_rate: float) -> np.ndarray:
        """清掃完了率を表示するステータスバーを生成する。"""
        bar = np.zeros((50, width, 3), dtype=np.uint8)
        cleaned_cells = round(cleaning_rate * 24)
        text = f"Cleaning: {cleaned_cells}/24 ({cleaning_rate * 100:.1f}%)  [q: quit]"
        cv2.putText(
            bar, text, (10, 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2,
        )
        return bar

    def _draw_alert(self, img: np.ndarray) -> np.ndarray:
        """清掃完了アラートを半透明オーバーレイで描画する。"""
        overlay = img.copy()
        h, w = img.shape[:2]

        # 半透明の黒オーバーレイ
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        result = cv2.addWeighted(overlay, 0.4, img, 0.6, 0)

        # 「清掃完了！」テキスト
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

    def wait_key(self, delay_ms: int = 1) -> str | None:
        """キー入力を待機し、押されたキーを返す。

        Args:
            delay_ms: 待機時間（ミリ秒）

        Returns:
            押されたキー文字、なければ None
        """
        key = cv2.waitKey(delay_ms) & 0xFF
        if key == 255:  # キー入力なし
            return None
        return chr(key)

    def destroy(self) -> None:
        """ウィンドウを破棄する。"""
        cv2.destroyWindow(self._window_name)
