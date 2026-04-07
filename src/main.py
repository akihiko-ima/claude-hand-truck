"""CleanTrack アプリケーションのエントリーポイント。

全コンポーネントを初期化し、メインループを制御する。
"""

import sys
import os
# python src/main.py で直接実行された場合にプロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

import logging
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.app_config import load_config
from src.detection.calibration_manager import CalibrationManager
from src.detection.hand_detector import HandDetector
from src.input.camera_manager import CameraManager
from src.output.display_controller import DebugImageSaver
from src.output.heatmap_renderer import HeatmapRenderer
from src.storage.data_storage import DataStorage
from src.tracking.grid_tracker import GridTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

console = Console()

# アプリケーション設定
CAMERA_IDS = [0, 1]    # 使用するカメラID
TABLE_ID = "table_01"  # テーブル識別子
OUTPUTS_DIR = Path("outputs")


def main() -> None:
    """CleanTrack メインエントリーポイント。"""
    debug_mode = "debug" in sys.argv

    console.print(Panel(
        Text("CleanTrack 清掃モニタリング", justify="center"),
        style="bold cyan",
        padding=(1, 4),
    ))

    if debug_mode:
        OUTPUTS_DIR.mkdir(exist_ok=True)
        console.print(f"[yellow]デバッグモード: 画像を {OUTPUTS_DIR}/debug.jpg に1秒ごとに保存します[/]")
        debug_saver = DebugImageSaver(OUTPUTS_DIR)

    # --- コンポーネント初期化 ---
    config = load_config()
    calib_manager = CalibrationManager()
    storage = DataStorage()
    tracker = GridTracker(
        rows=config.grid.rows,
        cols=config.grid.cols,
        clean_threshold_seconds=config.grid.clean_threshold_seconds,
    )
    renderer = HeatmapRenderer()

    # カメラ初期化
    camera_manager = CameraManager(CAMERA_IDS)

    # キャリブレーション設定の読み込みまたは実施
    calibrations = {}
    for cam_id in CAMERA_IDS:
        calib_config = calib_manager.load_config(cam_id)
        if calib_config is None:
            console.print(f"[yellow]カメラ {cam_id} のキャリブレーション設定が見つかりません。キャリブレーションを開始します。[/]")
            frames = camera_manager.get_frames()
            if cam_id not in frames:
                console.print(f"[bold red]カメラ {cam_id} が接続されていません。終了します。[/]")
                camera_manager.release()
                return
            calib_config = calib_manager.run_calibration(cam_id, frames[cam_id])
        calibrations[cam_id] = calib_config
        console.print(f"[green]✓ カメラ {cam_id} のキャリブレーション設定を読み込みました。[/]")

    # MediaPipe 手検出エンジンの初期化
    try:
        with console.status("[cyan]手検出エンジンを初期化しています...[/]", spinner="dots"):
            detector = HandDetector(calib_manager)
    except RuntimeError as e:
        console.print(f"[bold red]{e}[/]")
        camera_manager.release()
        return

    # 清掃セッションの開始
    session = storage.create_session(TABLE_ID)
    tracker.reset()
    console.print(Panel(
        f"[green]セッション ID: {session.session_id}[/]\n[dim]Ctrl+C で終了します[/]",
        title="[bold green]清掃セッション開始[/]",
        border_style="green",
    ))

    prev_time = time.time()
    last_save_time = 0.0

    # --- メインループ ---
    try:
        while True:
            frames = camera_manager.get_frames()
            if not frames:
                logger.warning("フレームを取得できませんでした。次のフレームに進みます。")
                continue

            # delta_time の計算
            current_time = time.time()
            delta_time = current_time - prev_time
            prev_time = current_time

            # 全カメラの手検出結果をマージ（マルチカメラ論理和統合）
            all_positions = []
            annotated_frames = {}
            for cam_id, frame in frames.items():
                calib = calibrations.get(cam_id)
                if calib is None:
                    annotated_frames[cam_id] = frame
                    continue
                positions = detector.detect(frame, cam_id, calib)
                all_positions.extend(positions)
                annotated = detector.draw_landmarks(frame, positions)

                # キャリブレーションエリアを半透明ポリゴンで描画
                pts = np.array(calib.table_corners, dtype=np.int32)
                overlay = annotated.copy()
                cv2.fillPoly(overlay, [pts], (0, 200, 255))
                annotated = cv2.addWeighted(overlay, 0.12, annotated, 0.88, 0)
                cv2.polylines(annotated, [pts], True, (0, 200, 255), 2)
                cv2.putText(
                    annotated, f"Cam{cam_id} table area", (pts[0][0], pts[0][1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1,
                )
                annotated_frames[cam_id] = annotated

            # グリッドトラッカーの更新
            tracker.update(all_positions, delta_time)
            grid = tracker.get_grid()
            cleaning_rate = tracker.get_cleaning_rate()

            # セッションデータの更新と都度保存
            session.grid_cells = grid
            session.cleaning_rate = cleaning_rate
            heatmap = renderer.render(grid)
            storage.save_session(session, heatmap)

            # デバッグモード: 1秒ごとに画像を保存
            if debug_mode and (current_time - last_save_time >= 1.0):
                debug_saver.save(annotated_frames, heatmap, cleaning_rate)
                last_save_time = current_time

    except KeyboardInterrupt:
        console.print("\n[yellow]Ctrl+C が押されました。終了します。[/]")
    finally:
        # --- 終了処理 ---
        session.ended_at = datetime.now().isoformat()
        session.cleaning_rate = tracker.get_cleaning_rate()
        heatmap = renderer.render(tracker.get_grid())
        storage.save_session(session, heatmap)

        console.print(Panel(
            f"[green]完了率: {session.cleaning_rate * 100:.1f}%[/]\n"
            f"[dim]保存先: data/sessions/{session.session_id}/[/]",
            title="[bold green]セッション保存完了[/]",
            border_style="green",
        ))

        detector.close()
        camera_manager.release()
        console.print("[dim]CleanTrack を終了しました。[/]")


if __name__ == "__main__":
    main()
