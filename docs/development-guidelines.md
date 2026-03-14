# 開発ガイドライン (Development Guidelines)

## コーディング規約

### 命名規則

#### 変数・関数

```python
# ✅ 良い例: 役割が明確
accumulated_seconds = 0.0
def calculate_cleaning_rate(grid: list[list[GridCell]]) -> float: ...

# ❌ 悪い例: 曖昧
sec = 0.0
def calc(g): ...
```

**原則**:

- 変数: `snake_case`、名詞または名詞句
- 関数: `snake_case`、動詞で始める
- 定数: `UPPER_SNAKE_CASE`
- Boolean: `is_`, `has_`, `should_` で始める

#### クラス・型

```python
# クラス: PascalCase、名詞
class GridTracker: ...
class CalibrationManager: ...

# dataclass のフィールド: snake_case
@dataclass
class GridCell:
    row: int
    accumulated_seconds: float
    is_cleaned: bool

# 型エイリアス: PascalCase
GridType = list[list[GridCell]]
```

#### プライベートメンバー

```python
class GridTracker:
    def update(self, ...) -> None: ...          # パブリックメソッド
    def _position_to_cell(self, ...) -> ...: ...  # プライベートメソッド（単一アンダースコア）
```

---

### コードフォーマット

- **インデント**: スペース4つ（Pythonの標準）
- **行の長さ**: 最大120文字
- **型ヒント**: すべての関数・メソッドに型ヒントを付与する

```python
# ✅ 良い例: 型ヒントあり
def detect(self, frame: np.ndarray, camera_id: int, calib: CalibrationConfig) -> list[HandPosition]:
    ...

# ❌ 悪い例: 型ヒントなし
def detect(self, frame, camera_id, calib):
    ...
```

---

### コメント規約

**関数・クラスのドキュメント**:

```python
def update(self, hand_positions: list[HandPosition], delta_time: float) -> None:
    """手座標と経過時間でグリッドを更新する。

    検出されたセルの累積清掃時間を加算し、清掃完了判定を行う。
    マルチカメラの結果は呼び出し元で統合済みのリストを渡すこと。

    Args:
        hand_positions: 検出された手座標のリスト（空リストも許容）
        delta_time: 前フレームからの経過時間（秒）
    """
```

**インラインコメント**:

```python
# ✅ 良い例: なぜそうするかを説明
# 境界チェック: 検出座標が正規化範囲(0-1)を超えた場合に丸める
col = min(int(x * self.COLS), self.COLS - 1)

# ❌ 悪い例: コードを読めばわかることを書く
# colを計算する
col = min(int(x * self.COLS), self.COLS - 1)
```

---

### エラーハンドリング

**原則**:
- 予期されるエラー（カメラ切断・ファイル不正）は適切に処理してユーザーに日本語でメッセージを表示
- 予期しないエラーは上位に伝播させてログに記録
- エラーを握りつぶさない（`except: pass` は禁止）

```python
# ✅ 良い例: 予期されるエラーを分類して処理
try:
    config = self.load_config(camera_id)
except FileNotFoundError:
    print(f"カメラ{camera_id}の設定ファイルが見つかりません。再キャリブレーションが必要です。")
    return None
except json.JSONDecodeError as e:
    print(f"設定ファイルが破損しています。再設定が必要です。")
    logger.error(f"Calibration config parse error: {e}")
    return None

# ❌ 悪い例: エラーを無視
try:
    config = self.load_config(camera_id)
except Exception:
    pass  # 問題の原因が追跡不能になる
```

---

### マジックナンバーの排除

```python
# ✅ 良い例: クラス定数として定義
class GridTracker:
    ROWS = 2
    COLS = 12
    CLEAN_THRESHOLD_SECONDS = 5.0

# ❌ 悪い例: マジックナンバー
if cell.accumulated_seconds >= 5.0:  # この5.0は何？
    cell.is_cleaned = True
```

---

## Git運用ルール

### ブランチ戦略

**ブランチ構成**:

```
main (本番リリース済み・安定版)
└── develop (開発・統合)
    ├── feature/{機能名}   # 新機能開発
    ├── fix/{修正内容}     # バグ修正
    └── refactor/{対象}   # リファクタリング
```

**運用ルール**:

- `main`: タグでバージョン管理。直接コミット禁止
- `develop`: PRレビュー後にのみマージ。CIでの自動テスト必須
- `feature/*`, `fix/*`: `develop` から分岐し、完了後にPRで `develop` へマージ
- **マージ方針**: `feature→develop` は squash merge 推奨

---

### コミットメッセージ規約

**フォーマット（Conventional Commits）**:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type一覧**:

| Type | 用途 |
|------|------|
| `feat` | 新機能 |
| `fix` | バグ修正 |
| `docs` | ドキュメントのみの変更 |
| `refactor` | リファクタリング（機能変更なし） |
| `test` | テスト追加・修正 |
| `chore` | ビルド・依存関係更新など |

**良いコミットメッセージの例**:

```
feat(tracking): グリッドセルの累積時間加算ロジックを実装

手の正規化座標をグリッドセル(row, col)に変換し、
delta_timeを累積することで清掃時間を管理する。
5秒以上の累積で is_cleaned = True に設定。

Closes #12
```

---

### プルリクエストプロセス

**作成前のチェック**:

- [ ] 全てのテストがパス (`uv run pytest`)
- [ ] 型チェックがパス (`uv run mypy src/`)
- [ ] 競合が解決されている

**PRテンプレート**:

```markdown
## 変更の種類
- [ ] 新機能 (feat)
- [ ] バグ修正 (fix)
- [ ] リファクタリング (refactor)
- [ ] ドキュメント (docs)
- [ ] その他 (chore)

## 変更内容
### 何を変更したか
[簡潔な説明]

### なぜ変更したか
[背景・理由]

## テスト
- [ ] ユニットテスト追加
- [ ] 統合テスト追加 / 手動テスト実施

## 関連Issue
Closes #[番号]

## レビューポイント
[レビュアーに特に見てほしい点]
```

---

## テスト戦略

### テストピラミッド

```
       /\
      /E2E\       少（手動テスト）
     /------\
    / 統合   \     中（動画ファイル入力）
   /----------\
  / ユニット   \   多（pytest）
 /--------------\
```

**目標比率**: ユニット70% / 統合20% / E2E10%

### ユニットテストの書き方（Given-When-Then）

```python
# ✅ 良い例: Given-When-Then パターン
def test_is_cleaned_when_accumulated_5_seconds():
    # Given: 準備
    tracker = GridTracker()

    # When: 実行（5秒分のdelta_timeで複数回更新）
    position = HandPosition(x_normalized=0.1, y_normalized=0.1, ...)
    tracker.update([position], delta_time=5.0)

    # Then: 検証
    cell = tracker.get_grid()[0][1]
    assert cell.is_cleaned is True
    assert cell.accumulated_seconds >= 5.0
```

**テスト関数命名規則**:

```python
# パターン: test_{テスト対象}_{条件}_when_{期待結果}
def test_update_empty_positions_does_not_increment(): ...
def test_position_to_cell_boundary_value_returns_valid_cell(): ...
def test_cleaning_rate_all_cleaned_returns_1_0(): ...
```

### カバレッジ目標

| 対象 | カバレッジ目標 |
|------|--------------|
| `src/tracking/` (コアビジネスロジック) | 80%以上 |
| `src/detection/` (座標変換) | 80%以上 |
| `src/storage/` (データ永続化) | 70%以上 |
| `src/input/`, `src/output/` (I/O) | 50%以上（カメラ依存のため） |

---

## コードレビュー基準

### レビューポイント

**機能性**:
- [ ] 機能設計書・PRDの要件を満たしているか
- [ ] グリッド境界値（row:0-1, col:0-11）が適切に処理されているか
- [ ] マルチカメラの検出結果が正しく統合されているか

**可読性**:
- [ ] 命名が明確か（特にドメイン固有の用語: `accumulated_seconds`, `calibration` など）
- [ ] 複雑な座標変換ロジックにコメントがあるか

**保守性**:
- [ ] 閾値等の定数が `UPPER_SNAKE_CASE` の定数として定義されているか
- [ ] 外部ライブラリ依存（OpenCV、MediaPipe）が対応コンポーネントに閉じているか

**パフォーマンス**:
- [ ] フレームループ内で重い初期化処理をしていないか
- [ ] 不要なデータコピーがないか（NumPy配列の参照渡し等）

### レビューコメントの書き方

```markdown
[必須] この処理はフレームループ内で毎回実行されています。
       MediaPipe の初期化はコンストラクタで1度だけ行ってください。

[推奨] CLEAN_THRESHOLD_SECONDS をメソッド内にハードコードせず、
       クラス定数として定義することで、将来の閾値変更が容易になります。

[提案] `_position_to_cell()` の境界値チェックをユニットテストに追加すると
       安全性が高まります。

[質問] delta_time が負になるケースはありえますか？
       カメラ再接続時のタイムスタンプ処理を確認したいです。
```

---

## 開発環境セットアップ

### 必要なツール

| ツール | バージョン | 用途 |
|--------|-----------|------|
| VS Code | 最新 | エディタ |
| Docker Desktop | 最新 | devcontainer実行 |
| Dev Containers拡張 | 最新 | VS Code devcontainer統合 |

### セットアップ手順

```bash
# 1. リポジトリのクローン
git clone <URL>
cd claude-hand-truck

# 2. VS Code で開く
code .

# 3. devcontainer で再オープン
# コマンドパレット: "Dev Containers: Reopen in Container"

# 4. 依存関係のインストール（コンテナ内で実行）
uv sync

# 5. アプリケーションの起動
uv run python src/main.py

# 6. テストの実行
uv run pytest tests/

# 7. 型チェック
uv run mypy src/
```

### 推奨 VS Code 拡張

- **Python** (Microsoft): Python言語サポート
- **Pylance**: 高速な型チェックとインテリセンス
- **Black Formatter**: コードフォーマッター
- **Ruff**: 高速なPython Linter

---

## 実装チェックリスト

実装完了前に確認:

### コード品質

- [ ] 型ヒントが全関数・メソッドに付与されている
- [ ] マジックナンバーがない（定数として定義済み）
- [ ] `except: pass` がない
- [ ] 関数が単一の責務を持っている（目安: 50行以内）

### 依存関係

- [ ] OpenCV/MediaPipe への依存が `src/input/`, `src/detection/` に閉じている
- [ ] `src/tracking/` が外部ライブラリ（OpenCV等）に依存していない
- [ ] `src/models/` が他の `src/` レイヤーに依存していない

### テスト

- [ ] ユニットテストが書かれている
- [ ] `uv run pytest` が全パス
- [ ] 境界値（グリッドのrow/col最大値）がテストされている

### ドキュメント

- [ ] 関数・クラスにdocstringがある
- [ ] 複雑な座標変換ロジックにコメントがある
