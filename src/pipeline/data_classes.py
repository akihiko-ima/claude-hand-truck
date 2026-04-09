"""パイプライン内スレッド間で受け渡すデータクラスの定義。"""

from dataclasses import dataclass, field

import numpy as np

from src.models.hand_position import HandPosition


@dataclass
class SyncFrameItem:
    """2台のカメラから同期して取得したフレームペア。"""

    frame_index: int
    timestamp: int  # Unix時刻（ミリ秒）
    frames: dict[int, np.ndarray]  # {camera_id: frame}


@dataclass
class DetectionResultItem:
    """優先度付き手検出の結果。CalibrationManager変換済みの HandPosition を保持する。"""

    frame_index: int
    timestamp: int  # Unix時刻（ミリ秒）
    source_camera_id: int | None  # 検出に使用したカメラID（未検出時は None）
    hand_positions: list[HandPosition] = field(default_factory=list)
    detected: bool = False
    # 採用した右手の生ランドマーク21点（画像正規化座標）。CSV書き出しに使用
    raw_landmarks: list[tuple[float, float, float]] = field(default_factory=list)
    # デバッグモード時のみ格納。通常時は None でメモリを節約する
    frames: dict[int, np.ndarray] | None = None
