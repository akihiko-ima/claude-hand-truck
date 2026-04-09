"""CleanTrack アプリケーションのエントリーポイント。

全コンポーネントを初期化し、HandDetectionPipeline を起動する。
"""

import sys
import os
# python src/main.py で直接実行された場合にプロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

import logging

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.app_config import load_config
from src.detection.calibration_manager import CalibrationManager
from src.pipeline.pipeline import HandDetectionPipeline

logger = logging.getLogger(__name__)

console = Console()

TABLE_ID = "table_01"


def _run_calibration(config, calib_manager: CalibrationManager) -> dict | None:
    """キャリブレーション設定を読み込む、または対話的キャリブレーションを実施する。

    Returns:
        {camera_id: CalibrationConfig} の辞書。いずれかのカメラが失敗した場合は None。
    """
    import cv2
    calibrations = {}

    # 一時的にカメラをオープンしてキャリブレーション用フレームを取得
    caps = {}
    for cam_id in config.pipeline.camera_ids:
        cap = cv2.VideoCapture(cam_id)
        if cap.isOpened():
            caps[cam_id] = cap

    for cam_id in config.pipeline.camera_ids:
        calib_config = calib_manager.load_config(cam_id)
        if calib_config is None:
            console.print(
                f"[yellow]カメラ {cam_id} のキャリブレーション設定が見つかりません。キャリブレーションを開始します。[/]"
            )
            cap = caps.get(cam_id)
            if cap is None:
                console.print(f"[bold red]カメラ {cam_id} が接続されていません。終了します。[/]")
                for c in caps.values():
                    c.release()
                return None
            ret, frame = cap.read()
            if not ret:
                console.print(f"[bold red]カメラ {cam_id} からフレームを取得できません。終了します。[/]")
                for c in caps.values():
                    c.release()
                return None
            calib_config = calib_manager.run_calibration(cam_id, frame)
        calibrations[cam_id] = calib_config
        console.print(f"[green]✓ カメラ {cam_id} のキャリブレーション設定を読み込みました。[/]")

    for cap in caps.values():
        cap.release()

    return calibrations


def main() -> None:
    """CleanTrack メインエントリーポイント。"""
    debug_mode = "debug" in sys.argv
    log_mode = "log" in sys.argv

    logging.basicConfig(
        level=logging.DEBUG if log_mode else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    console.print(Panel(
        Text("CleanTrack 清掃モニタリング", justify="center"),
        style="bold cyan",
        padding=(1, 4),
    ))

    if debug_mode:
        console.print("[yellow]デバッグモード: 画像を outputs/debug.jpg に1秒ごとに保存します[/]")
    if log_mode:
        console.print("[yellow]ログモード: DEBUGレベルのログをターミナルに出力します[/]")

    config = load_config()
    calib_manager = CalibrationManager()

    calibrations = _run_calibration(config, calib_manager)
    if calibrations is None:
        return

    pipeline = HandDetectionPipeline(
        config=config,
        calib_manager=calib_manager,
        calibrations=calibrations,
        table_id=TABLE_ID,
        debug_mode=debug_mode,
        log_mode=log_mode,
    )

    try:
        pipeline.start()
        pipeline.wait()
    except Exception as e:
        logger.error(f"パイプライン実行中に例外が発生しました: {e}")
        pipeline.stop()

    console.print("[dim]CleanTrack を終了しました。[/]")


if __name__ == "__main__":
    main()
