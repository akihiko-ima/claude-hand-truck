"""
手のランドマーク アニメーション（30 FPS + シークバー付き）

依存:
    pip install matplotlib pandas numpy

使い方:
    python animate_hand.py
    python animate_hand.py --csv hand_landmarks_cam1.csv
    python animate_hand.py --save output.gif    # GIF 保存（要 Pillow）
    python animate_hand.py --save output.mp4    # MP4 保存（要 ffmpeg）
"""

import argparse
from pathlib import Path
import tomllib

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Slider
import pandas as pd


# ============================================================
# 定数
# ============================================================
def _load_settings() -> dict:
    defaults = {
        "fps": 30,
        "default_csv": "output/hand_landmarks.csv",
    }
    config_path = Path(__file__).resolve().parents[1] / "settings.toml"
    if not config_path.exists():
        return defaults
    with config_path.open("rb") as f:
        data = tomllib.load(f)
    loaded = data.get("animation", {})
    return {
        "fps": int(loaded.get("fps", defaults["fps"])),
        "default_csv": str(loaded.get("default_csv", defaults["default_csv"])),
    }


SETTINGS = _load_settings()
FPS = SETTINGS["fps"]
INTERVAL_MS = int(1000 / FPS)  # 33 ms

HAND_CONNECTIONS = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (0, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (0, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (5, 9),
    (9, 13),
    (13, 17),
]

FINGER_COLORS = {
    "thumb": ("#e05c3a", [0, 1, 2, 3, 4]),
    "index": ("#3a7de0", [0, 5, 6, 7, 8]),
    "middle": ("#3ab87d", [0, 9, 10, 11, 12]),
    "ring": ("#9b59b6", [0, 13, 14, 15, 16]),
    "pinky": ("#e0aa3a", [0, 17, 18, 19, 20]),
    "palm": ("#888888", [5, 9, 13, 17]),
}


def _connection_color(s, e):
    for _, (color, nodes) in FINGER_COLORS.items():
        if s in nodes and e in nodes:
            return color
    return "#888888"


NODE_COLORS = ["#888888"] * 21
for _, (_c, _ns) in FINGER_COLORS.items():
    for _n in _ns:
        NODE_COLORS[_n] = _c
NODE_COLORS[0] = "#ffffff"


# ============================================================
# データ読み込み
# ============================================================
def load_frames(csv_path: str) -> list:
    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError(f"データが1行もありません: {csv_path}")

    has_camera_id = "source_camera_id" in df.columns

    frames = []
    for _, row in df.iterrows():
        detected = int(row["detected"]) == 1
        camera_id = "-"
        if has_camera_id:
            raw_camera_id = row["source_camera_id"]
            if pd.notna(raw_camera_id):
                camera_id = str(raw_camera_id)
        if detected:
            xs = [float(row[f"lm{i}_x"]) for i in range(21)]
            ys = [float(row[f"lm{i}_y"]) for i in range(21)]
        else:
            xs, ys = None, None
        frames.append(
            {
                "frame_index": int(row["frame_index"]),
                "detected": detected,
                "source_camera_id": camera_id,
                "xs": xs,
                "ys": ys,
            }
        )
    return frames


# ============================================================
# アニメーション構築
# ============================================================
def build_animation(frames: list, save_path: str = None):
    n_frames = len(frames)
    total_sec = frames[-1]["frame_index"] / FPS

    def fmt_time(sec: float) -> str:
        m = int(sec) // 60
        s = sec - m * 60
        return f"{m:02d}:{s:05.2f}"

    # --------------------------------------------------------
    # レイアウト
    # --------------------------------------------------------
    fig = plt.figure(figsize=(6, 6.8), facecolor="#1a1a2e")

    # メイン描画エリア
    ax = fig.add_axes([0.05, 0.13, 0.90, 0.83])
    ax.set_xlim(0, 1)
    ax.set_ylim(1, 0)  # MediaPipe: 左上原点・y下向き
    ax.set_aspect("equal")
    ax.set_facecolor("#1a1a2e")
    ax.tick_params(colors="#555566")
    for spine in ax.spines.values():
        spine.set_edgecolor("#333344")

    # シークバー Axes
    ax_seek = fig.add_axes([0.10, 0.04, 0.80, 0.03], facecolor="#2a2a3e")
    ax_seek.set_xlim(0, total_sec)
    ax_seek.set_ylim(0, 1)
    ax_seek.set_xticks([])
    ax_seek.set_yticks([])
    for spine in ax_seek.spines.values():
        spine.set_edgecolor("#444455")

    # 進捗バー（塗り）と現在位置ライン
    # fill_between は更新が難しいので Rectangle で代用
    from matplotlib.patches import Rectangle

    progress_bar = Rectangle(
        (0, 0), 0, 1, facecolor="#3a7de0", alpha=0.5, transform=ax_seek.transData
    )
    ax_seek.add_patch(progress_bar)

    # 現在位置の縦線
    # ★ slider.set_val() は一切使わない → stale コールバック再帰を回避
    progress_line = ax_seek.axvline(x=0, color="#ffffff", linewidth=1.5)

    # 時間ラベル
    time_now = fig.text(
        0.10, 0.085, "00:00.00", color="#aaaaaa", fontsize=8, ha="left", va="bottom"
    )
    time_total = fig.text(
        0.90,
        0.085,
        fmt_time(total_sec),
        color="#555566",
        fontsize=8,
        ha="right",
        va="bottom",
    )

    # --------------------------------------------------------
    # 描画オブジェクト
    # --------------------------------------------------------
    line_objects = {}
    for s, e in HAND_CONNECTIONS:
        (line,) = ax.plot(
            [], [], "-", color=_connection_color(s, e), linewidth=1.8, alpha=0.85
        )
        line_objects[(s, e)] = line

    scatter = ax.scatter([], [], s=40, zorder=5)

    info_text = ax.text(
        0.01, 0.01, "", transform=ax.transAxes, color="#aaaaaa", fontsize=9, va="bottom"
    )

    label_texts = [
        ax.text(
            0,
            0,
            str(i),
            color="#ffffff",
            fontsize=6,
            ha="center",
            va="bottom",
            visible=False,
        )
        for i in range(21)
    ]

    # --------------------------------------------------------
    # 状態管理
    # --------------------------------------------------------
    state = {"idx": 0, "paused": False}

    # --------------------------------------------------------
    # 描画更新
    # ★ slider.set_val() を完全に廃止
    #   → progress_line / progress_bar の xdata を直接更新するだけ
    # --------------------------------------------------------
    def render(idx: int):
        idx = max(0, min(idx, n_frames - 1))
        f = frames[idx]
        elapsed = f["frame_index"] / FPS

        if f["detected"]:
            xs, ys = f["xs"], f["ys"]
            for (s, e), line in line_objects.items():
                line.set_data([xs[s], xs[e]], [ys[s], ys[e]])
            scatter.set_offsets(np.column_stack([xs, ys]))
            scatter.set_color(NODE_COLORS)
            for i, t in enumerate(label_texts):
                t.set_position((xs[i], ys[i] - 0.02))
                t.set_visible(True)
        else:
            # 未検出フレーム → 描画をクリア
            for line in line_objects.values():
                line.set_data([], [])
            scatter.set_offsets(np.empty((0, 2)))
            for t in label_texts:
                t.set_visible(False)

        progress_line.set_xdata([elapsed, elapsed])
        progress_bar.set_width(elapsed)

        detected_str = "detected" if f["detected"] else "no detection"
        info_text.set_text(
            f"frame {f['frame_index']}  |  {idx + 1} / {n_frames}"
            f"  |  {fmt_time(elapsed)}  |  cam {f['source_camera_id']}  |  {detected_str}"
        )
        time_now.set_text(fmt_time(elapsed))

    # --------------------------------------------------------
    # FuncAnimation
    # --------------------------------------------------------
    def init():
        scatter.set_offsets(np.empty((0, 2)))
        for line in line_objects.values():
            line.set_data([], [])
        info_text.set_text("")
        for t in label_texts:
            t.set_visible(False)
        return list(line_objects.values()) + [scatter, info_text] + label_texts

    def update(frame_idx):
        if not state["paused"]:
            state["idx"] = frame_idx
            render(frame_idx)
        return list(line_objects.values()) + [scatter, info_text] + label_texts

    anim = animation.FuncAnimation(
        fig,
        update,
        frames=n_frames,
        init_func=init,
        interval=INTERVAL_MS,
        blit=False,
    )

    # --------------------------------------------------------
    # シークバー クリック / ドラッグ（保存時は不要）
    # --------------------------------------------------------
    if save_path is None:

        def on_seek(event):
            # ax_seek 上のクリック・ドラッグで時刻ジャンプ
            if event.inaxes != ax_seek:
                return
            target_sec = np.clip(event.xdata, 0, total_sec)
            target_fi = target_sec * FPS
            idx = min(
                range(n_frames), key=lambda i: abs(frames[i]["frame_index"] - target_fi)
            )
            state["idx"] = idx
            state["paused"] = True
            render(idx)
            fig.canvas.draw_idle()

        def on_release(event):
            if event.inaxes == ax_seek:
                state["paused"] = False

        fig.canvas.mpl_connect("button_press_event", on_seek)
        fig.canvas.mpl_connect("motion_notify_event", on_seek)
        fig.canvas.mpl_connect("button_release_event", on_release)

    return fig, anim


# ============================================================
# エントリーポイント
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=SETTINGS["default_csv"])
    parser.add_argument(
        "--save", default=None, help="保存先 (.gif 要Pillow / .mp4 要ffmpeg)"
    )
    args = parser.parse_args()

    if args.save:
        save_path = Path(args.save).resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        args.save = str(save_path)

    print(f"[INFO] CSV 読み込み: {args.csv}")
    frames = load_frames(args.csv)
    total_sec = frames[-1]["frame_index"] / FPS
    print(f"[INFO] 検出フレーム数: {len(frames)}  |  総経過時間: {total_sec:.2f} 秒")

    fig, anim = build_animation(frames, save_path=args.save)

    if args.save:
        suffix = Path(args.save).suffix.lower()
        if suffix == ".gif":
            writer = animation.PillowWriter(fps=FPS)
        elif suffix == ".mp4":
            writer = animation.FFMpegWriter(fps=FPS, bitrate=1800)
        else:
            raise ValueError(f"未対応の拡張子: {suffix}")
        n = len(frames)
        print(f"[INFO] 保存中: {args.save}  (全 {n} フレーム)")

        def progress(current_frame, total_frames):
            pct = current_frame / total_frames * 100
            bar = "#" * (current_frame * 30 // total_frames)
            print(
                f"\r  [{bar:<30}] {current_frame:4d}/{total_frames}  {pct:5.1f}%",
                end="",
                flush=True,
            )

        anim.save(args.save, writer=writer, dpi=120, progress_callback=progress)
        print(f"\n[INFO] 保存完了: {args.save}")
    else:
        print("[INFO] シークバーをクリック／ドラッグで任意の時刻にジャンプできます")
        plt.show()


if __name__ == "__main__":
    main()
