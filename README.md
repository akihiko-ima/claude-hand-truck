# 清掃作業可視化ツール

## 1. 本プロジェクトについて
- 仮想顧客設定
レストランにおいて、各テーブルが清掃されているかを可視化するツールを作成し、清掃漏れを検出する。

- 開発方針
仕様駆動開発（SDD）を基本として、動作確認を行う。

## 2. セットアップ

```bash
# uvのインストール
curl -LsSf https://astral.sh/uv/install.sh | sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 依存パッケージのインストール
uv sync
```

## 3. 使い方

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
   - 設定は `config/calibration_0.json` に保存され、次回から自動読み込み

2. **清掃セッション開始**
   - ヘッドレスで動作し、手の検出結果をリアルタイムに処理
   - 手をテーブル上で動かすと各マスが清掃済みに変化（5秒以上で清掃完了）
   - デバッグモード時は `outputs/debug.jpg` にカメラ映像 + ヒートマップを1秒ごとに保存

3. **終了**
   - `Ctrl+C` で終了
   - セッションデータが `data/sessions/{タイムスタンプ}/` に保存される

### カメラ映像の確認

カメラの接続・位置確認をしたいときに使います。

```bash
uv run scripts/view_cameras.py
```

- 接続中のカメラ（Camera 0・Camera 1）を別ウィンドウに表示
- 接続されていないカメラはスキップ
- `q` キーで終了

### デュアルカメラを使う場合

**1. キャリブレーション設定スクリプトを実行**

```bash
uv run  scripts/setup_calibration.py
```

- Camera 0・Camera 1 の順にウィンドウが開く
- 各カメラ映像上でテーブルの4頂点を**時計回りにクリック**（左上→右上→右下→左下）
- `r` キーでクリックをリセット
- 両カメラ完了後に**相互補正プレビュー**が表示される
  - Camera 0・Camera 1 それぞれの俯瞰ビューとブレンド結果を確認
  - 両カメラの映像が一致していれば `s` キーで保存
  - ずれていれば `r` キーで最初からやり直し
- 設定は `config/calibration_0.json` と `config/calibration_1.json` に保存される

**2. `src/main.py` のカメラ設定を変更**

```python
CAMERA_IDS = [0, 1]  # カメラ2台使用
```

## 4. テスト

```bash
uv run pytest
```