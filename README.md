# 清掃作業可視化ツール (CleanTrack)

レストランのテーブル清掃状況をデュアルカメラで可視化し、清掃漏れを検出するツール。

---

## 採用技術

| 技術 | バージョン | 用途 |
|------|-----------|------|
| Python | 3.12.x | 実行環境 |
| OpenCV | 4.x | カメラ映像取得・ホモグラフィ変換・描画 |
| MediaPipe | 最新安定版 | 手骨格ランドマーク検出 |
| NumPy | 2.x | 座標変換行列演算 |
| rich | 13.x | TUI (コンソール表示) |
| uv | 0.5.x | パッケージ管理・実行 |

---

## 座標変換の仕組み（デュアルカメラ対応）

```
[カメラ映像 (ピクセル座標)]
        ↓  ホモグラフィ変換（透視変換）
[テーブル正規化座標 (0.0〜1.0)]
        ↓  グリッドマッピング
[グリッドセル (row, col)]
```

### 1. キャリブレーション（初回のみ）

テーブルを真上から見たときの座標系に射影するため、**透視変換行列（ホモグラフィ行列）** を事前に算出する。

1. カメラ映像上でテーブルの4頂点を時計回りにクリック（左上→右上→右下→左下）
2. `cv2.findHomography()` で、4頂点をテーブル正規化座標の4隅 `(0,0)(1,0)(1,1)(0,1)` に対応付けた 3×3 変換行列を算出
3. 変換行列を `config/calibration_{camera_id}.json` に保存

各カメラが**独立した変換行列**を持つため、カメラの設置位置・角度が異なっていても正確に変換できる。

### 2. フレームごとの座標変換

```
手首ランドマーク (MediaPipe 出力 → 0.0〜1.0 の正規化座標)
    ↓  フレームサイズを乗算
カメラ画素座標 (px, py)
    ↓  cv2.perspectiveTransform(src, homography_matrix)
テーブル正規化座標 (x_norm, y_norm)  ← 0.0〜1.0 でテーブル全体を表現
    ↓  floor(x_norm * cols), floor(y_norm * rows)
グリッドセル (row, col)
```

### 3. デュアルカメラの統合（論理和）

```
Camera 0: ピクセル座標 → 行列0 → 正規化座標 → HandPosition リスト
Camera 1: ピクセル座標 → 行列1 → 正規化座標 → HandPosition リスト
                                                        ↓ リストをマージ
                                              GridTracker.update() で一括処理
```

同一フレーム内で同一セルへの重複検出は1回のみ計上（set で重複排除）。
これにより、2台のカメラの死角を補完しながら正確な清掃時間を計測する。

---

## システム構成

```
src/
├── main.py              # エントリーポイント・メインループ
├── app_config.py        # config/config.toml 読み込み
├── input/
│   └── camera_manager.py    # OpenCV カメラ管理
├── detection/
│   ├── hand_detector.py     # MediaPipe 手検出 + 座標変換
│   └── calibration_manager.py  # ホモグラフィ計算・保存・読み込み
├── tracking/
│   └── grid_tracker.py      # グリッド状態管理・清掃完了判定
├── output/
│   ├── heatmap_renderer.py  # ヒートマップ画像生成
│   └── display_controller.py   # デバッグ画像保存
├── storage/
│   └── data_storage.py      # セッションデータ JSON 保存
└── models/                  # 共有 dataclass 定義
```

---

## セットアップ

```bash
# uv のインストール
curl -LsSf https://astral.sh/uv/install.sh | sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 依存パッケージのインストール
uv sync
```

---

## 設定 (config/config.toml)

`config/config.toml` でグリッド設定を変更できる。

```toml
[grid]
rows = 3                    # グリッドの行数（縦分割数）
cols = 7                    # グリッドの列数（横分割数）
clean_threshold_seconds = 3.0  # 清掃完了と判定する累積秒数
```

`config/config.toml` が存在しない場合はデフォルト値（3行×7列、3.0秒）が使用される。

---

## 使い方

### アプリ起動

```bash
# 通常起動（ヘッドレス）
uv run src/main.py

# デバッグモード（outputs/debug.jpg を1秒ごとに上書き保存）
uv run src/main.py debug
```

### 起動後の流れ

1. **キャリブレーション**（初回のみ）
   - テーブルの4隅をマウスでクリックして座標を設定
   - 設定は `config/calibration_{camera_id}.json` に保存され、次回から自動読み込み

2. **清掃セッション開始**
   - ヘッドレスで動作し、手の検出結果をリアルタイムに処理
   - 手をテーブル上で動かすと各マスが清掃済みに変化（`clean_threshold_seconds` 以上で完了）
   - デバッグモード時は `outputs/debug.jpg` にカメラ映像＋ヒートマップを1秒ごとに保存

3. **終了**
   - `Ctrl+C` で終了
   - セッションデータが `data/sessions/{タイムスタンプ}/` に保存される

### カメラ映像の確認

```bash
uv run scripts/view_cameras.py
```

接続中のカメラ（Camera 0・Camera 1）を別ウィンドウに表示。`q` キーで終了。

### デュアルカメラのキャリブレーション

```bash
uv run scripts/setup_calibration.py
```

- Camera 0・Camera 1 の順にウィンドウが開く
- 各カメラ映像上でテーブルの4頂点を**時計回りにクリック**（左上→右上→右下→左下）
- `r` キーでクリックをリセット
- 両カメラ完了後に**相互補正プレビュー**が表示される（`s` で保存、`r` でやり直し）
- 設定は `config/calibration_0.json` と `config/calibration_1.json` に保存される

シングルカメラで運用する場合は `src/main.py` の `CAMERA_IDS = [0]` に変更する。

---
## 記録したデータの動画(mp4)確認
```bash
uv run .\tools\animate_hand.py --csv .\data\hand_landmarks.csv --save .\outputs\output.mp4
```

## zmqClient sample
```bash
uv run .\tools\sample_zmq_client.py
```


## テスト

```bash
uv run pytest
```

---

## データ出力

```
data/sessions/{YYYYMMDD_HHMMSS}/
├── session.json   # 清掃率・グリッド状態（フレームごとに上書き保存）
└── heatmap.png    # 最終ヒートマップ画像
```
