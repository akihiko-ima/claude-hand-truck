from dataclasses import dataclass, field


@dataclass
class GridCell:
    """グリッドセルの清掃状態を表すデータクラス。

    テーブルを縦2×横12に分割した24マスのうちの1セル。
    累積清掃時間が CLEAN_THRESHOLD_SECONDS (5.0秒) 以上になると清掃済みと判定する。
    """

    row: int
    col: int
    accumulated_seconds: float = field(default=0.0)
    is_cleaned: bool = field(default=False)
    last_hand_detected_at: float | None = field(default=None)
