"""MediaPipe モデルファイルをダウンロードするスクリプト。

使用方法:
    uv run python scripts/download_models.py
"""

import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).parent.parent / "models"

MODELS = {
    "hand_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/"
        "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
    ),
}


def download(name: str, url: str) -> None:
    dest = MODELS_DIR / name
    if dest.exists():
        print(f"  {name}: already exists, skip")
        return
    print(f"  {name}: downloading...")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    print(f"  {name}: done ({dest.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    print("Downloading MediaPipe models...")
    for model_name, model_url in MODELS.items():
        download(model_name, model_url)
    print("All models ready.")
