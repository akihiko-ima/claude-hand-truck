"""カメラ映像確認スクリプト。

接続中のカメラ映像をウィンドウに表示し続けます。
カメラの位置確認やケーブル接続確認に使用します。

使い方:
    uv run scripts/view_cameras.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

import cv2
from rich.console import Console
from rich.panel import Panel

console = Console()

CAMERA_IDS = [0, 1]
CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 480


def main() -> None:
    console.print(Panel(
        "[bold cyan]カメラ映像確認[/bold cyan]\n[dim]q キーで終了します[/dim]",
        padding=(1, 4),
    ))

    captures = {}
    with console.status("[cyan]カメラに接続しています...[/]", spinner="dots"):
        for cam_id in CAMERA_IDS:
            cap = cv2.VideoCapture(cam_id)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
                captures[cam_id] = cap
            else:
                cap.release()

        for cam_id in captures:
            cv2.namedWindow(f"Camera {cam_id}", cv2.WINDOW_NORMAL)
            cv2.resizeWindow(f"Camera {cam_id}", CAPTURE_WIDTH, CAPTURE_HEIGHT)

    if not captures:
        console.print("[bold red]接続できるカメラがありません。終了します。[/]")
        return

    for cam_id in captures:
        console.print(f"[green]✓ カメラ {cam_id} に接続しました[/]")
    console.print("[dim]q キーで終了します[/]")

    try:
        while True:
            for cam_id, cap in captures.items():
                ret, frame = cap.read()
                if ret:
                    cv2.imshow(f"Camera {cam_id}", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        for cap in captures.values():
            cap.release()
        cv2.destroyAllWindows()
        console.print("[dim]終了しました。[/]")


if __name__ == "__main__":
    main()
