"""カメラ映像確認スクリプト。

フロー:
  1. 検出カメラを全表示
  2. 使用するカメラを選択 → config.toml の camera_ids を更新
  3. 選択したカメラを表示
  4. Priorityカメラを選択 → config.toml の priority_camera_id を更新
  5. 最終確認として選択カメラを表示

使い方:
    uv run scripts/view_cameras.py
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from pathlib import Path

import cv2
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

console = Console()

CAMERA_IDS = [0, 1, 2, 3]
CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 480
CONFIG_PATH = Path("config/config.toml")


def _detect_cameras() -> dict[int, cv2.VideoCapture]:
    """接続中のカメラを検出して返す。"""
    captures: dict[int, cv2.VideoCapture] = {}
    for cam_id in CAMERA_IDS:
        cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
            captures[cam_id] = cap
        else:
            cap.release()
    return captures


def _show_cameras(
    captures: dict[int, cv2.VideoCapture],
    title: str,
    priority_id: int | None = None,
) -> None:
    """カメラ映像をウィンドウに表示する。q キーで閉じる。"""
    for cam_id in captures:
        cv2.namedWindow(f"Camera {cam_id}", cv2.WINDOW_NORMAL)
        cv2.resizeWindow(f"Camera {cam_id}", CAPTURE_WIDTH, CAPTURE_HEIGHT)

    console.print(f"[dim]{title} — q キーで閉じてください[/]")

    try:
        while True:
            for cam_id, cap in captures.items():
                ret, frame = cap.read()
                if ret:
                    is_priority = priority_id is not None and cam_id == priority_id
                    label = f"Camera {cam_id}  [PRIORITY]" if is_priority else f"Camera {cam_id}"
                    cv2.putText(
                        frame,
                        label,
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (180, 105, 255),
                        2,
                    )
                    cv2.imshow(f"Camera {cam_id}", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()


def _select_camera_ids(available_ids: list[int]) -> list[int]:
    """TUI で使用するカメラを選択させる（カンマ区切り入力）。"""
    tbl = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    tbl.add_column("カメラID", style="bold yellow", width=10)
    tbl.add_column("状態", style="green")
    for cam_id in available_ids:
        tbl.add_row(f"Camera {cam_id}", "接続済み")

    console.print(Panel(
        tbl,
        title="[bold cyan]使用するカメラの選択[/]",
        subtitle="使用するカメラIDをカンマ区切りで入力してください（例: 0,1）",
        border_style="cyan",
        padding=(1, 2),
    ))

    default = ",".join(str(i) for i in available_ids[:2])
    while True:
        raw = Prompt.ask(
            "[bold]カメラIDを入力[/bold]",
            default=default,
            console=console,
        )
        try:
            selected = sorted({int(x.strip()) for x in raw.split(",")})
        except ValueError:
            console.print("[red]数値をカンマ区切りで入力してください。[/]")
            continue

        invalid = [c for c in selected if c not in available_ids]
        if invalid:
            console.print(f"[red]接続されていないカメラID: {invalid}[/]")
            continue
        if len(selected) < 2:
            console.print("[red]2台以上のカメラを選択してください。[/]")
            continue

        return selected


def _select_priority_camera(camera_ids: list[int]) -> int:
    """TUI でPriorityカメラを選択させる。"""
    tbl = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    tbl.add_column("番号", style="bold yellow", width=6)
    tbl.add_column("カメラID", width=10)
    for i, cam_id in enumerate(camera_ids):
        tbl.add_row(str(i), f"Camera {cam_id}")

    console.print(Panel(
        tbl,
        title="[bold cyan]Priorityカメラの選択[/]",
        subtitle="手検出の優先カメラを選択してください",
        border_style="cyan",
        padding=(1, 2),
    ))

    choices = [str(i) for i in range(len(camera_ids))]
    choice = Prompt.ask(
        "[bold]番号を入力[/bold]",
        choices=choices,
        default="0",
        console=console,
    )
    return camera_ids[int(choice)]


def _update_camera_ids(camera_ids: list[int]) -> None:
    """config.toml の camera_ids を更新する。"""
    if not CONFIG_PATH.exists():
        console.print(f"[yellow]警告: {CONFIG_PATH} が見つかりません。スキップします。[/]")
        return

    toml_list = "[" + ", ".join(str(i) for i in camera_ids) + "]"
    text = CONFIG_PATH.read_text(encoding="utf-8")
    updated = re.sub(
        r"(?m)^camera_ids\s*=\s*\[.*?\]",
        f"camera_ids = {toml_list}",
        text,
    )
    CONFIG_PATH.write_text(updated, encoding="utf-8")
    console.print(f"[green]✓ config.toml を更新しました: camera_ids = {toml_list}[/]")


def _update_priority_camera_id(priority_camera_id: int) -> None:
    """config.toml の priority_camera_id を更新する。"""
    if not CONFIG_PATH.exists():
        console.print(f"[yellow]警告: {CONFIG_PATH} が見つかりません。スキップします。[/]")
        return

    text = CONFIG_PATH.read_text(encoding="utf-8")
    updated = re.sub(
        r"(?m)^priority_camera_id\s*=\s*\d+",
        f"priority_camera_id = {priority_camera_id}",
        text,
    )
    CONFIG_PATH.write_text(updated, encoding="utf-8")
    console.print(
        f"[green]✓ config.toml を更新しました: priority_camera_id = {priority_camera_id}[/]"
    )


def main() -> None:
    console.print(Panel(
        "[bold cyan]カメラセットアップ[/bold cyan]",
        padding=(1, 4),
    ))

    # カメラ検出
    captures: dict[int, cv2.VideoCapture] = {}
    with console.status("[cyan]カメラに接続しています...[/]", spinner="dots"):
        captures = _detect_cameras()

    if not captures:
        console.print("[bold red]接続できるカメラがありません。終了します。[/]")
        return

    for cam_id in captures:
        console.print(f"[green]✓ カメラ {cam_id} に接続しました[/]")

    # Step 1: 全カメラを表示
    _show_cameras(captures, "Step 1/3  全カメラの確認")

    # Step 2: 使用カメラを選択 → config.toml 更新
    available_ids = sorted(captures.keys())
    selected_ids = _select_camera_ids(available_ids)
    _update_camera_ids(selected_ids)

    selected_captures = {cam_id: captures[cam_id] for cam_id in selected_ids}

    # Step 3: 選択カメラを表示
    _show_cameras(selected_captures, "Step 2/3  選択したカメラの確認")

    # Step 4: Priorityカメラを選択 → config.toml 更新
    priority_id = _select_priority_camera(selected_ids)
    _update_priority_camera_id(priority_id)

    # Step 5: 最終確認
    _show_cameras(selected_captures, "Step 3/3  最終確認", priority_id=priority_id)

    # 全カメラ解放
    for cap in captures.values():
        cap.release()

    console.print("[bold green]✓ セットアップ完了[/]")


if __name__ == "__main__":
    main()
