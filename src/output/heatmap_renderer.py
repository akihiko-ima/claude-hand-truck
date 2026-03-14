import cv2
import numpy as np

from src.models.grid_cell import GridCell

# BGR カラー定義
COLOR_CLEANED = (0, 200, 0)    # 緑: 清掃済み (accumulated_seconds >= 5.0)
COLOR_IN_PROGRESS = (0, 200, 200)  # 黄: 清掃中 (0 < accumulated_seconds < 5.0)
COLOR_NOT_CLEANED = (0, 0, 200)    # 赤: 未清掃 (accumulated_seconds == 0)
COLOR_BORDER = (50, 50, 50)        # グリッド枠線


class HeatmapRenderer:
    """グリッド状態を3色ヒートマップ画像として生成するクラス。

    各セルの清掃状態に応じて色分けした画像を返す。
    OpenCV/NumPyのみで実装（matplotlib不要）。
    """

    def __init__(self, cell_width_px: int = 80, cell_height_px: int = 120) -> None:
        """ヒートマップのセルサイズを設定する。

        デフォルト値での画像サイズ: 80*12=960px × 120*2=240px

        Args:
            cell_width_px: 1セルの横幅（ピクセル）
            cell_height_px: 1セルの縦幅（ピクセル）
        """
        self._cell_w = cell_width_px
        self._cell_h = cell_height_px

    def render(self, grid: list[list[GridCell]]) -> np.ndarray:
        """グリッド状態をOpenCV画像(ndarray)として返す。

        Args:
            grid: GridCell の2次元配列 [row][col]

        Returns:
            ヒートマップ画像（BGR形式、ndarray）
        """
        rows = len(grid)
        cols = len(grid[0]) if rows > 0 else 0

        img_h = rows * self._cell_h
        img_w = cols * self._cell_w
        img = np.zeros((img_h, img_w, 3), dtype=np.uint8)

        for row_idx, row in enumerate(grid):
            for col_idx, cell in enumerate(row):
                color = self._get_cell_color(cell)
                y1 = row_idx * self._cell_h
                y2 = y1 + self._cell_h
                x1 = col_idx * self._cell_w
                x2 = x1 + self._cell_w

                # セルを塗りつぶす
                img[y1:y2, x1:x2] = color

                # 枠線を描画
                cv2.rectangle(img, (x1, y1), (x2 - 1, y2 - 1), COLOR_BORDER, 1)

                # 累積時間をテキスト表示
                text = f"{cell.accumulated_seconds:.1f}s"
                text_x = x1 + 4
                text_y = y1 + self._cell_h // 2 + 5
                cv2.putText(
                    img, text, (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1,
                )

        return img

    def _get_cell_color(self, cell: GridCell) -> tuple[int, int, int]:
        """セルの清掃状態に応じたBGR色を返す。"""
        if cell.is_cleaned:
            return COLOR_CLEANED
        elif cell.accumulated_seconds > 0:
            return COLOR_IN_PROGRESS
        else:
            return COLOR_NOT_CLEANED
