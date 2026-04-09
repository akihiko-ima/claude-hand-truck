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
    clean_threshold_seconds: float = 5.0


@dataclass
class HandDetectionConfig:
    right_hand_only: bool = True
    num_hands: int = 2
    min_detection_confidence: float = 0.5
    min_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5


@dataclass
class AppConfig:
    grid: GridConfig = field(default_factory=GridConfig)
    hand_detection: HandDetectionConfig = field(default_factory=HandDetectionConfig)


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
    return AppConfig(
        grid=GridConfig(
            rows=grid_data.get("rows", 3),
            cols=grid_data.get("cols", 7),
            clean_threshold_seconds=grid_data.get("clean_threshold_seconds", 5.0),
        ),
        hand_detection=HandDetectionConfig(
            right_hand_only=hd_data.get("right_hand_only", True),
            num_hands=hd_data.get("num_hands", 2),
            min_detection_confidence=hd_data.get("min_detection_confidence", 0.5),
            min_presence_confidence=hd_data.get("min_presence_confidence", 0.5),
            min_tracking_confidence=hd_data.get("min_tracking_confidence", 0.5),
        ),
    )
