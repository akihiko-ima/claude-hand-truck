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
class AppConfig:
    grid: GridConfig = field(default_factory=GridConfig)


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
    return AppConfig(grid=GridConfig(
        rows=grid_data.get("rows", 3),
        cols=grid_data.get("cols", 7),
        clean_threshold_seconds=grid_data.get("clean_threshold_seconds", 5.0),
    ))
