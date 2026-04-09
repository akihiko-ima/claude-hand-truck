"""アプリケーション設定の読み込みモジュール。

config.toml からアプリケーション設定を読み込む。
ファイルが存在しない場合はデフォルト値を使用する。
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GridConfig:
    rows: int = 3
    cols: int = 7
    clean_threshold_seconds: float = 3.0


@dataclass
class HandDetectionConfig:
    right_hand_only: bool = True
    num_hands: int = 2
    min_detection_confidence: float = 0.5
    min_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5


@dataclass
class PipelineConfig:
    target_fps: float = 30.0
    frame_queue_maxsize: int = 300
    priority_camera_id: int = 0
    camera_ids: list[int] = field(default_factory=lambda: [0, 1])


@dataclass
class CsvConfig:
    enabled: bool = True
    output_path: str = "data/hand_landmarks.csv"


@dataclass
class ZmqConfig:
    enabled: bool = True
    endpoint: str = "tcp://*:5555"


@dataclass
class AppConfig:
    grid: GridConfig = field(default_factory=GridConfig)
    hand_detection: HandDetectionConfig = field(default_factory=HandDetectionConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    csv: CsvConfig = field(default_factory=CsvConfig)
    zmq: ZmqConfig = field(default_factory=ZmqConfig)


def load_config(path: Path = Path("config/config.toml")) -> AppConfig:
    """TOML ファイルからアプリケーション設定を読み込む。

    ファイルが存在しない場合はデフォルト値の AppConfig を返す。

    Args:
        path: config.toml のパス（デフォルト: config/config.toml）

    Returns:
        AppConfig インスタンス
    """
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return AppConfig()

    grid_data = data.get("grid", {})
    hd_data = data.get("hand_detection", {})
    pl_data = data.get("pipeline", {})
    csv_data = data.get("csv", {})
    zmq_data = data.get("zmq", {})
    return AppConfig(
        grid=GridConfig(
            rows=grid_data.get("rows", 3),
            cols=grid_data.get("cols", 7),
            clean_threshold_seconds=grid_data.get("clean_threshold_seconds", 3.0),
        ),
        hand_detection=HandDetectionConfig(
            right_hand_only=hd_data.get("right_hand_only", True),
            num_hands=hd_data.get("num_hands", 2),
            min_detection_confidence=hd_data.get("min_detection_confidence", 0.5),
            min_presence_confidence=hd_data.get("min_presence_confidence", 0.5),
            min_tracking_confidence=hd_data.get("min_tracking_confidence", 0.5),
        ),
        pipeline=PipelineConfig(
            target_fps=float(pl_data.get("target_fps", 30.0)),
            frame_queue_maxsize=int(pl_data.get("frame_queue_maxsize", 300)),
            priority_camera_id=int(pl_data.get("priority_camera_id", 0)),
            camera_ids=list(pl_data.get("camera_ids", [0, 1])),
        ),
        csv=CsvConfig(
            enabled=bool(csv_data.get("enabled", True)),
            output_path=str(csv_data.get("output_path", "data/hand_landmarks.csv")),
        ),
        zmq=ZmqConfig(
            enabled=bool(zmq_data.get("enabled", True)),
            endpoint=str(zmq_data.get("endpoint", "tcp://*:5555")),
        ),
    )
