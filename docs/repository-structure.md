# リポジトリ構造定義書 (Repository Structure Document)

## プロジェクト構造

```
claude-hand-truck/
├── src/                        # ソースコード
│   ├── main.py                 # エントリーポイント: コンポーネント初期化・メインループ
│   ├── input/                  # 入力レイヤー: カメラ管理
│   ├── detection/              # 検出レイヤー: 手検出・キャリブレーション
│   ├── tracking/               # ビジネスロジックレイヤー: グリッドトラッキング
│   ├── output/                 # 出力レイヤー: ヒートマップ・表示
│   ├── storage/                # データレイヤー: データ永続化
│   └── models/                 # 共有データモデル (dataclasses)
├── tests/                      # テストコード
│   ├── unit/                   # ユニットテスト
│   └── integration/            # 統合テスト
├── docs/                       # プロジェクトドキュメント
│   ├── ideas/                  # ブレスト・アイデアメモ
│   ├── product-requirements.md
│   ├── functional-design.md
│   ├── architecture.md
│   ├── repository-structure.md
│   ├── development-guidelines.md
│   └── glossary.md
├── config/                     # キャリブレーション設定ファイル (実行時生成)
├── data/                       # 清掃セッションデータ (実行時生成)
│   └── sessions/
│       └── {YYYYMMDD_HHMMSS}/
│           ├── session.json
│           └── heatmap.png
├── .steering/                  # 作業単位のドキュメント
├── .claude/                    # Claude Code 設定
├── .devcontainer/              # devcontainer 設定
├── pyproject.toml              # プロジェクト設定・依存関係定義
├── uv.lock                     # 依存関係ロックファイル
├── CLAUDE.md                   # Claude Code プロジェクト指示書
└── README.md                   # プロジェクト概要・セットアップ手順
```

---

## ディレクトリ詳細

### src/ (ソースコードディレクトリ)

#### src/models/

**役割**: プロジェクト全体で共有するデータモデルの定義。他の全レイヤーから参照される。

**配置ファイル**:

- `grid_cell.py`: `GridCell` dataclass
- `hand_position.py`: `HandPosition` dataclass
- `calibration_config.py`: `CalibrationConfig` dataclass
- `cleaning_session.py`: `CleaningSession` dataclass

**命名規則**:

- ファイル名: `snake_case.py`
- クラス名: `PascalCase`
- フィールド名: `snake_case`

**依存関係**:

- 依存可能: Python標準ライブラリ、NumPy（型ヒントのみ）
- 依存禁止: 他の `src/` 配下ディレクトリ（循環依存防止）

---

#### src/main.py

**役割**: アプリケーションのエントリーポイント。全コンポーネントの初期化・メインループの制御・終了処理を担う。

**責務**:

- キャリブレーション設定の有無を確認し、キャリブレーションモードまたは清掃モードで起動
- `CameraManager`, `HandDetector`, `CalibrationManager`, `GridTracker`, `HeatmapRenderer`, `DisplayController`, `DataStorage` を初期化
- フレームループの管理（フレーム取得 → 検出 → 追跡 → 表示 → 保存）
- `q` キー入力を受け取り、セッションデータを保存して終了

**依存関係**:

- 依存可能: `src/` 配下のすべてのレイヤー（唯一の例外。エントリーポイントのため）

---

#### src/input/

**役割**: カメラデバイスの初期化・フレーム取得・再接続管理。OpenCV のカメラ操作を閉じ込める。

**配置ファイル**:

- `camera_manager.py`: `CameraManager` クラス

**命名規則**:

- ファイル名: `snake_case.py`
- クラス名: `PascalCase`

**依存関係**:

- 依存可能: `src/models/`、OpenCV
- 依存禁止: `src/detection/`、`src/tracking/`、`src/output/`、`src/storage/`

---

#### src/detection/

**役割**: MediaPipeによる手検出と、ホモグラフィ変換を使ったキャリブレーション管理。カメラ座標をテーブル正規化座標に変換する責務を持つ。

**配置ファイル**:

- `hand_detector.py`: `HandDetector` クラス（MediaPipe手検出）
- `calibration_manager.py`: `CalibrationManager` クラス（マウスUI・ホモグラフィ計算・設定保存）

**命名規則**:

- ファイル名: `snake_case.py`
- クラス名: `PascalCase`

**依存関係**:

- 依存可能: `src/models/`、OpenCV、MediaPipe、NumPy
- 依存禁止: `src/tracking/`、`src/output/`、`src/storage/`

---

#### src/tracking/

**役割**: グリッドセルの状態管理・累積清掃時間の計算・清掃完了判定。ビジネスロジックを担うコアレイヤー。外部ライブラリへの依存を最小化し、テストを容易にする。

**配置ファイル**:

- `grid_tracker.py`: `GridTracker` クラス

**命名規則**:

- ファイル名: `snake_case.py`
- クラス名: `PascalCase`
- 定数: `UPPER_SNAKE_CASE`（例: `CLEAN_THRESHOLD_SECONDS = 5.0`）

**依存関係**:

- 依存可能: `src/models/`、Python標準ライブラリ、NumPy
- 依存禁止: `src/input/`、`src/detection/`、`src/output/`、`src/storage/`、OpenCV、MediaPipe

---

#### src/output/

**役割**: グリッド状態のヒートマップ画像生成と、OpenCVウィンドウへの統合表示。

**配置ファイル**:

- `heatmap_renderer.py`: `HeatmapRenderer` クラス（グリッド→色付き画像変換）
- `display_controller.py`: `DisplayController` クラス（統合画面表示・キー入力処理）

**命名規則**:

- ファイル名: `snake_case.py`
- クラス名: `PascalCase`

**依存関係**:

- 依存可能: `src/models/`、OpenCV、NumPy、matplotlib
- 依存禁止: `src/input/`、`src/detection/`、`src/tracking/`、`src/storage/`

---

#### src/storage/

**役割**: 清掃セッションデータのJSON保存・読み込みと、ヒートマップ画像の保存。横断的関心事として他のどのレイヤーからも利用可能。

**配置ファイル**:

- `data_storage.py`: `DataStorage` クラス

**命名規則**:

- ファイル名: `snake_case.py`
- クラス名: `PascalCase`

**依存関係**:

- 依存可能: `src/models/`、Python標準ライブラリ、NumPy、OpenCV（PNG保存のみ）
- 依存禁止: `src/input/`、`src/detection/`、`src/tracking/`、`src/output/`

---

### tests/ (テストディレクトリ)

#### tests/unit/

**役割**: 各クラスの単体テスト。外部デバイス（カメラ）への依存なし。

**構造**:

```
tests/unit/
├── tracking/
│   └── test_grid_tracker.py        # GridTracker のユニットテスト
├── detection/
│   └── test_calibration_manager.py # CalibrationManager のユニットテスト
└── storage/
    └── test_data_storage.py        # DataStorage のユニットテスト
```

**命名規則**:

- ファイル名: `test_{対象クラスのsnake_case}.py`
- テスト関数名: `test_{テスト内容}_when_{条件}` 形式
  - 例: `test_is_cleaned_when_accumulated_5_seconds()`

---

#### tests/integration/

**役割**: 複数コンポーネントを組み合わせた統合テスト。動画ファイルを入力として使用。

**構造**:

```
tests/integration/
├── fixtures/                       # テスト用動画・設定ファイル
│   ├── sample_video.mp4
│   └── calibration_0.json
└── test_cleaning_pipeline.py       # 検出→追跡→保存の一連フローテスト
```

---

### docs/ (ドキュメントディレクトリ)

**配置ドキュメント**:

- `ideas/`: ブレスト・アイデアメモ（自由形式）
- `product-requirements.md`: プロダクト要求定義書
- `functional-design.md`: 機能設計書
- `architecture.md`: アーキテクチャ設計書
- `repository-structure.md`: リポジトリ構造定義書（本ドキュメント）
- `development-guidelines.md`: 開発ガイドライン
- `glossary.md`: 用語集

---

### config/ (設定ファイルディレクトリ)

**役割**: キャリブレーション設定ファイルの保存先。アプリケーション実行時に自動生成される。

**配置ファイル**:

- `calibration_{camera_id}.json`: カメラごとのキャリブレーション設定

**注意**: `config/` ディレクトリは `.gitignore` に追加し、環境固有の設定をリポジトリに含めない。

---

### data/ (データディレクトリ)

**役割**: 清掃セッションデータの保存先。アプリケーション実行時に自動生成される。

**注意**: `data/` ディレクトリは `.gitignore` に追加し、業務データをリポジトリに含めない。

---

## ファイル配置規則

### ソースファイル

| ファイル種別 | 配置先 | 命名規則 | 例 |
|------------|--------|---------|-----|
| データモデル | `src/models/` | `snake_case.py` | `grid_cell.py` |
| 入力コンポーネント | `src/input/` | `snake_case.py` | `camera_manager.py` |
| 検出コンポーネント | `src/detection/` | `snake_case.py` | `hand_detector.py` |
| ビジネスロジック | `src/tracking/` | `snake_case.py` | `grid_tracker.py` |
| 出力コンポーネント | `src/output/` | `snake_case.py` | `heatmap_renderer.py` |
| データ永続化 | `src/storage/` | `snake_case.py` | `data_storage.py` |

### テストファイル

| テスト種別 | 配置先 | 命名規則 | 例 |
|-----------|--------|---------|-----|
| ユニットテスト | `tests/unit/{レイヤー名}/` | `test_{対象}.py` | `test_grid_tracker.py` |
| 統合テスト | `tests/integration/` | `test_{機能}.py` | `test_cleaning_pipeline.py` |

---

## 命名規則

### ディレクトリ名

- **レイヤーディレクトリ**: `snake_case`（複数形）
  - 例: `models/`, `detection/`, `tracking/`

### Pythonファイル名

- **クラスファイル**: `snake_case.py`（Pythonの慣習に従う）
  - 例: `grid_tracker.py`, `hand_detector.py`
- **テストファイル**: `test_` プレフィックス + `snake_case.py`
  - 例: `test_grid_tracker.py`

### クラス・関数・変数名

| 種別 | 規則 | 例 |
|------|------|-----|
| クラス名 | PascalCase | `GridTracker`, `HandDetector` |
| メソッド名 | snake_case | `update()`, `get_cleaning_rate()` |
| 変数名 | snake_case | `accumulated_seconds`, `camera_id` |
| 定数名 | UPPER_SNAKE_CASE | `CLEAN_THRESHOLD_SECONDS`, `ROWS` |
| プライベートメンバー | `_snake_case` プレフィックス | `_position_to_cell()` |

---

## 依存関係のルール

### レイヤー間の依存（許可）

```
src/input/
    ↓
src/detection/  ← src/models/
    ↓
src/tracking/   ← src/models/
    ↓
src/output/     ← src/models/
    ↑
src/storage/    ← src/models/
```

**禁止される依存**:

- `src/tracking/` → `src/detection/`（ビジネスロジックが検出実装に依存しない）
- `src/tracking/` → `src/output/`（ビジネスロジックが表示に依存しない）
- `src/models/` → 任意の `src/{layer}/`（モデルは純粋なデータ定義のみ）

### 循環依存の禁止

各モジュールは単方向依存のみ許可。循環依存が発生する場合は `src/models/` に共通型を切り出す。

---

## 除外設定

### .gitignore

```
# Python
__pycache__/
*.py[cod]
.venv/

# uv
.python-version

# 実行時生成ディレクトリ
config/
data/

# ログ
*.log

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/settings.json
```
