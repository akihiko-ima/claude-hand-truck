# 要求内容 (Requirements)

## 実装対象機能

CleanTrack の全P0機能を一括実装する。

## 機能一覧

1. **データモデル** - GridCell, HandPosition, CalibrationConfig, CleaningSession dataclass
2. **CameraManager** - カメラ初期化・フレーム取得・再接続
3. **CalibrationManager** - マウスUIによる4頂点指定・ホモグラフィ変換・設定保存
4. **HandDetector** - MediaPipeによる手座標検出・テーブル座標変換
5. **GridTracker** - 24グリッド管理・累積清掃時間・清掃完了判定
6. **HeatmapRenderer** - 3色ヒートマップ画像生成
7. **DisplayController** - 統合画面表示・キー入力処理・清掃完了アラート
8. **DataStorage** - セッションJSON保存・読み込み
9. **main.py** - 全コンポーネント統合・メインループ
10. **pyproject.toml** - 依存関係定義
11. **ユニットテスト** - GridTracker, CalibrationManager, DataStorage

## 参照ドキュメント

- docs/functional-design.md（コンポーネント設計・アルゴリズム）
- docs/architecture.md（技術スタック・パフォーマンス要件）
- docs/repository-structure.md（ディレクトリ構造・命名規則）
- docs/development-guidelines.md（コーディング規約）
