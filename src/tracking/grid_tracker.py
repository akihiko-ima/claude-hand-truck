import time

from src.models.grid_cell import GridCell
from src.models.hand_position import HandPosition


class GridTracker:
    """テーブルのグリッドセルの清掃状態を管理するクラス。

    各セルの累積清掃時間を追跡し、clean_threshold_seconds 以上で清掃完了と判定する。
    マルチカメラの検出結果は呼び出し元でリストをマージして渡すこと（論理和統合）。
    """

    def __init__(
        self,
        rows: int = 2,
        cols: int = 12,
        clean_threshold_seconds: float = 5.0,
    ) -> None:
        self.ROWS = rows
        self.COLS = cols
        self.CLEAN_THRESHOLD_SECONDS = clean_threshold_seconds
        self._grid = self._create_grid()

    def _create_grid(self) -> list[list[GridCell]]:
        """全セルを初期状態で生成する。"""
        return [
            [GridCell(row=r, col=c) for c in range(self.COLS)]
            for r in range(self.ROWS)
        ]

    def update(self, hand_positions: list[HandPosition], delta_time: float) -> None:
        """手座標と経過時間でグリッドを更新する。

        今フレームで検出されたセルのみ累積時間を加算する。
        同一セルへの重複検出は1フレームあたり1回のみ加算（setで重複排除）。

        Args:
            hand_positions: 検出された手座標のリスト（空リストも許容）
            delta_time: 前フレームからの経過時間（秒）
        """
        detected_cells: set[tuple[int, int]] = set()
        for pos in hand_positions:
            row, col = self._position_to_cell(pos)
            detected_cells.add((row, col))

        for row, col in detected_cells:
            cell = self._grid[row][col]
            cell.accumulated_seconds += delta_time
            cell.last_hand_detected_at = time.time()
            cell.is_cleaned = cell.accumulated_seconds >= self.CLEAN_THRESHOLD_SECONDS

    def get_grid(self) -> list[list[GridCell]]:
        """現在のグリッド状態を返す。"""
        return self._grid

    def get_cleaning_rate(self) -> float:
        """清掃完了率を返す（0.0〜1.0）。

        Returns:
            清掃済みセル数 / 24
        """
        cleaned = sum(
            1
            for row in self._grid
            for cell in row
            if cell.is_cleaned
        )
        return cleaned / (self.ROWS * self.COLS)

    def reset(self) -> None:
        """グリッドを初期状態にリセットする（セッション開始時に使用）。"""
        self._grid = self._create_grid()

    def _position_to_cell(self, position: HandPosition) -> tuple[int, int]:
        """テーブル正規化座標をグリッドの(row, col)に変換する。

        境界値は最大インデックスに丸める。

        Args:
            position: テーブル正規化座標の手位置

        Returns:
            (row, col) タプル
        """
        col = min(int(position.x_normalized * self.COLS), self.COLS - 1)
        row = min(int(position.y_normalized * self.ROWS), self.ROWS - 1)
        # 負の値は0に丸める
        col = max(col, 0)
        row = max(row, 0)
        return row, col
