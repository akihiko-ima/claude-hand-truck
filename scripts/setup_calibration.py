"""デュアルカメラキャリブレーション設定スクリプト。

2台のカメラでテーブルの4頂点を指定し、相互補正プレビューを確認して
config/ ディレクトリに保存します。

使い方:
    uv run python scripts/setup_calibration.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

import cv2
import numpy as np
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.detection.calibration_manager import CalibrationManager
from src.models.calibration_config import CalibrationConfig

console = Console()

CAMERA_IDS = [0, 1]

# テーブル俯瞰プレビューのサイズ (幅:高さ ≒ 1800mm:300mm = 6:1)
PREVIEW_WIDTH = 1200
PREVIEW_HEIGHT = 200


def _capture_frame(cam_id: int) -> tuple[cv2.VideoCapture, np.ndarray] | None:
    """カメラを起動して静止フレームを1枚取得する。"""
    cap = cv2.VideoCapture(cam_id)
    if not cap.isOpened():
        console.print(f"[bold red]エラー: カメラ {cam_id} を開けませんでした。[/]")
        return None
    ret, frame = cap.read()
    if not ret:
        console.print(f"[bold red]エラー: カメラ {cam_id} のフレーム取得に失敗しました。[/]")
        cap.release()
        return None
    return cap, frame


def _calibrate_camera(cam_id: int, frame: np.ndarray) -> list[tuple[int, int]] | None:
    """静止フレーム上でテーブルの4頂点をクリック指定する。

    Args:
        cam_id: カメラID
        frame: キャリブレーションに使用する静止フレーム

    Returns:
        4頂点のリスト (左上→右上→右下→左下)。キャンセル時は None。
    """
    clicked: list[tuple[int, int]] = []
    window_name = f"Calibration - Camera {cam_id}"
    display_frame = frame.copy()

    def mouse_callback(event: int, x: int, y: int, flags: int, param: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN and len(clicked) < 4:
            clicked.append((x, y))

    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, mouse_callback)

    guide = Table.grid(padding=(0, 2))
    guide.add_column(style="bold yellow")
    guide.add_column()
    guide.add_row("順番", "左上(1) → 右上(2) → 右下(3) → 左下(4)")
    guide.add_row("r キー", "クリックをリセット")
    guide.add_row("q キー", "終了")

    console.print(Panel(
        guide,
        title=f"[bold cyan]カメラ {cam_id} キャリブレーション[/]",
        subtitle="テーブルの4頂点を時計回りにクリックしてください",
        border_style="cyan",
    ))

    labels = ["TL(1)", "TR(2)", "BR(3)", "BL(4)"]

    while True:
        show = display_frame.copy()

        for i, pt in enumerate(clicked):
            cv2.circle(show, pt, 8, (0, 255, 0), -1)
            cv2.putText(
                show, labels[i], (pt[0] + 10, pt[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
            )

        if len(clicked) >= 2:
            pts = np.array(clicked, dtype=np.int32)
            cv2.polylines(show, [pts], len(clicked) == 4, (0, 255, 0), 2)

        if len(clicked) < 4:
            msg = f"Next: {labels[len(clicked)]}  ({len(clicked)}/4)"
        else:
            msg = "Done! (4/4)"
        cv2.putText(show, msg, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        cv2.imshow(window_name, show)

        if len(clicked) == 4:
            cv2.waitKey(600)
            break

        key = cv2.waitKey(30) & 0xFF
        if key == ord("r"):
            clicked.clear()
            console.print("[yellow]リセットしました。再度クリックしてください。[/]")
        elif key == ord("q"):
            cv2.destroyWindow(window_name)
            return None

    cv2.destroyWindow(window_name)
    console.print(f"[bold green]✓ カメラ {cam_id} の4頂点を取得しました。[/]")
    return clicked


def _warp_to_table_view(frame: np.ndarray, corners: list[tuple[int, int]]) -> np.ndarray:
    """カメラフレームをテーブル俯瞰ビューにホモグラフィ変換する。"""
    src = np.array(corners, dtype=np.float32)
    dst = np.array(
        [[0, 0], [PREVIEW_WIDTH, 0], [PREVIEW_WIDTH, PREVIEW_HEIGHT], [0, PREVIEW_HEIGHT]],
        dtype=np.float32,
    )
    H, _ = cv2.findHomography(src, dst)
    return cv2.warpPerspective(frame, H, (PREVIEW_WIDTH, PREVIEW_HEIGHT))


def _show_blend_preview(
    config0: CalibrationConfig,
    config1: CalibrationConfig,
    frame0: np.ndarray,
    frame1: np.ndarray,
) -> bool:
    """両カメラの俯瞰ビューをブレンドして相互補正プレビューを表示する。

    Returns:
        True = 保存して完了、False = 最初からやり直し
    """
    warped0 = _warp_to_table_view(frame0, config0.table_corners)
    warped1 = _warp_to_table_view(frame1, config1.table_corners)
    blended = cv2.addWeighted(warped0, 0.5, warped1, 0.5, 0)

    def _labeled(img: np.ndarray, text: str) -> np.ndarray:
        out = img.copy()
        cv2.putText(out, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        return out

    sep = np.full((8, PREVIEW_WIDTH, 3), 60, dtype=np.uint8)
    panel = np.vstack([
        _labeled(warped0, f"Camera {CAMERA_IDS[0]}"),
        sep,
        _labeled(warped1, f"Camera {CAMERA_IDS[1]}"),
        sep,
        _labeled(blended, "Blend"),
    ])

    guide_h = 45
    guide_bar = np.zeros((guide_h, PREVIEW_WIDTH, 3), dtype=np.uint8)
    cv2.putText(
        guide_bar, "s: save & done  /  r: retry  /  q: quit",
        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 200, 200), 1,
    )
    panel = np.vstack([panel, guide_bar])

    key_guide = Table.grid(padding=(0, 2))
    key_guide.add_column(style="bold green")
    key_guide.add_column()
    key_guide.add_column(style="bold yellow")
    key_guide.add_column()
    key_guide.add_column(style="bold red")
    key_guide.add_column()
    key_guide.add_row("s", "保存して完了", "r", "最初からやり直す", "q", "終了")

    console.print(Panel(
        key_guide,
        title="[bold cyan]相互補正プレビュー[/]",
        subtitle="Camera 0 と Camera 1 の俯瞰ビューが一致していれば補正成功",
        border_style="cyan",
    ))

    window_name = "Blend Preview"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, PREVIEW_WIDTH, panel.shape[0])
    cv2.imshow(window_name, panel)

    result = False
    while True:
        key = cv2.waitKey(30) & 0xFF
        if key == ord("s"):
            result = True
            break
        elif key == ord("r") or key == ord("q"):
            result = False
            break

    cv2.destroyWindow(window_name)
    return result


def main() -> None:
    """デュアルカメラキャリブレーションのメインフロー。"""
    console.print(Panel(
        Text("CleanTrack デュアルカメラキャリブレーション設定", justify="center"),
        style="bold cyan",
        padding=(1, 4),
    ))

    # カメラ起動
    result0: tuple[cv2.VideoCapture, np.ndarray] | None = None
    result1: tuple[cv2.VideoCapture, np.ndarray] | None = None

    with console.status("[cyan]カメラを起動しています...[/]", spinner="dots"):
        result0 = _capture_frame(CAMERA_IDS[0])
        result1 = _capture_frame(CAMERA_IDS[1])

    if result0 is None or result1 is None:
        console.print(Panel(
            "[bold red]カメラの起動に失敗しました。接続を確認してください。[/]",
            border_style="red",
        ))
        if result0:
            result0[0].release()
        if result1:
            result1[0].release()
        sys.exit(1)

    console.print(f"[green]✓ カメラ {CAMERA_IDS[0]} / カメラ {CAMERA_IDS[1]} を起動しました。[/]")

    cap0, frame0 = result0
    cap1, frame1 = result1
    manager = CalibrationManager()

    try:
        while True:
            # Camera 0 キャリブレーション
            corners0 = _calibrate_camera(CAMERA_IDS[0], frame0)
            if corners0 is None:
                console.print("[yellow]キャリブレーションをキャンセルしました。[/]")
                break

            # Camera 1 キャリブレーション
            corners1 = _calibrate_camera(CAMERA_IDS[1], frame1)
            if corners1 is None:
                console.print("[yellow]キャリブレーションをキャンセルしました。[/]")
                break

            # CalibrationConfig を生成（保存はプレビュー確認後）
            config0 = manager._build_config(CAMERA_IDS[0], corners0)
            config1 = manager._build_config(CAMERA_IDS[1], corners1)

            # 相互補正プレビュー
            should_save = _show_blend_preview(config0, config1, frame0, frame1)

            if should_save:
                with console.status("[cyan]設定を保存しています...[/]", spinner="dots"):
                    manager.save_config(config0)
                    manager.save_config(config1)

                saved_table = Table(show_header=False, box=None, padding=(0, 1))
                saved_table.add_column(style="green")
                saved_table.add_row(f"config/calibration_{CAMERA_IDS[0]}.json")
                saved_table.add_row(f"config/calibration_{CAMERA_IDS[1]}.json")

                console.print(Panel(
                    saved_table,
                    title="[bold green]✓ 保存完了[/]",
                    border_style="green",
                ))
                break

            console.print("[yellow]最初からやり直します。[/]")
            ret0, frame0 = cap0.read()
            ret1, frame1 = cap1.read()
            if not ret0 or not ret1:
                console.print("[bold red]フレームの再取得に失敗しました。終了します。[/]")
                break
    finally:
        cap0.release()
        cap1.release()
        cv2.destroyAllWindows()

    console.print("[dim]完了しました。[/]")


if __name__ == "__main__":
    main()
