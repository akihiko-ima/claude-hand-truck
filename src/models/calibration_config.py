from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


@dataclass
class CalibrationConfig:
    """カメラキャリブレーション設定を表すデータクラス。

    カメラ映像上のテーブル4頂点とホモグラフィ変換行列を保持する。
    table_corners は時計回りで指定: 左上→右上→右下→左下
    """

    camera_id: int
    table_corners: list[tuple[int, int]]  # [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
    homography_matrix: "np.ndarray | None" = field(default=None)
    created_at: str = field(default="")
