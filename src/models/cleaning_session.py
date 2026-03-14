from dataclasses import dataclass, field

from .grid_cell import GridCell


@dataclass
class CleaningSession:
    """清掃セッション全体のデータを表すデータクラス。

    セッションIDはYYYYMMDD_HHMMSS形式。
    grid_cells は [row][col] の2次元配列 (2×12)。
    """

    session_id: str
    table_id: str
    started_at: str
    ended_at: str | None = field(default=None)
    grid_cells: list[list[GridCell]] = field(default_factory=list)
    cleaning_rate: float = field(default=0.0)
