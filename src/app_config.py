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
class AppConfig:
    grid: GridConfig = field(default_factory=GridConfig)


def load_config(path: Path = Path("config.toml")) -> AppConfig:
    """TOML ファイルからアプリケーション設定を読み込む。

    ファイルが存在しない場合はデフォルト値の AppConfig を返す。

    Args:
        path: config.toml のパス（デフォルト: プロジェクトルートの config.toml）

    Returns:
        AppConfig インスタンス
    """
    if not path.exists():
        return AppConfig()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    grid_data = data.get("grid", {})
    defaults = GridConfig()
    grid = GridConfig(
        rows=grid_data.get("rows", defaults.rows),
        cols=grid_data.get("cols", defaults.cols),
        clean_threshold_seconds=grid_data.get(
            "clean_threshold_seconds", defaults.clean_threshold_seconds
        ),
    )
    return AppConfig(grid=grid)
