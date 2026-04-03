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

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.detection.calibration_manager import CalibrationManager
from src.detection.hand_detector import HandDetector
from src.input.camera_manager import CameraManager
from src.output.display_controller import DisplayController
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
CAMERA_IDS = [0]       # 使用するカメラID (デュアルカメラの場合は [0, 1])
TABLE_ID = "table_01"  # テーブル識別子


def main() -> None:
    """CleanTrack メインエントリーポイント。"""
    console.print(Panel(
        Text("CleanTrack 清掃モニタリング", justify="center"),
        style="bold cyan",
        padding=(1, 4),
    ))

    # --- コンポーネント初期化 ---
    calib_manager = CalibrationManager()
    storage = DataStorage()
    tracker = GridTracker()
    renderer = HeatmapRenderer()
    display = DisplayController()

    # カメラ初期化
    camera_manager = CameraManager(CAMERA_IDS)

    # キャリブレーション設定の読み込みまたは実施
    calibrations = {}
    for cam_id in CAMERA_IDS:
        config = calib_manager.load_config(cam_id)
        if config is None:
            console.print(f"[yellow]カメラ {cam_id} のキャリブレーション設定が見つかりません。キャリブレーションを開始します。[/]")
            frames = camera_manager.get_frames()
            if cam_id not in frames:
                console.print(f"[bold red]カメラ {cam_id} が接続されていません。終了します。[/]")
                camera_manager.release()
                display.destroy()
                return
            config = calib_manager.run_calibration(cam_id, frames[cam_id])
        calibrations[cam_id] = config
        console.print(f"[green]✓ カメラ {cam_id} のキャリブレーション設定を読み込みました。[/]")

    # MediaPipe 手検出エンジンの初期化
    try:
        with console.status("[cyan]手検出エンジンを初期化しています...[/]", spinner="dots"):
            detector = HandDetector(calib_manager)
    except RuntimeError as e:
        console.print(f"[bold red]{e}[/]")
        camera_manager.release()
        display.destroy()
        return

    # 清掃セッションの開始
    session = storage.create_session(TABLE_ID)
    tracker.reset()
    console.print(Panel(
        f"[green]セッション ID: {session.session_id}[/]\n[dim]q キーで終了します[/]",
        title="[bold green]清掃セッション開始[/]",
        border_style="green",
    ))

    prev_time = time.time()

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
                annotated_frames[cam_id] = detector.draw_landmarks(frame, positions)

            # グリッドトラッカーの更新
            tracker.update(all_positions, delta_time)
            grid = tracker.get_grid()
            cleaning_rate = tracker.get_cleaning_rate()

            # セッションデータの更新と都度保存
            session.grid_cells = grid
            session.cleaning_rate = cleaning_rate
            heatmap = renderer.render(grid)
            storage.save_session(session, heatmap)

            # 統合画面の表示
            display.show(annotated_frames, heatmap, cleaning_rate)

            # キー入力の処理
            key = display.wait_key(delay_ms=1)
            if key == "q":
                console.print("[dim]終了キーが押されました。[/]")
                break

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
        display.destroy()
        console.print("[dim]CleanTrack を終了しました。[/]")


if __name__ == "__main__":
    main()
