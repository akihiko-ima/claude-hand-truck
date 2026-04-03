# タスクリスト (Tasklist)

## フェーズ1: プロジェクト設定

- [x] pyproject.toml を作成（Python 3.12, opencv-python, mediapipe, numpy, matplotlib, pytest）
- [x] src/__init__.py を作成
- [x] ディレクトリ構造（src/models, src/input, src/detection, src/tracking, src/output, src/storage）を作成

## フェーズ2: データモデル

- [x] src/models/__init__.py を作成
- [x] src/models/grid_cell.py を実装（GridCell dataclass）
- [x] src/models/hand_position.py を実装（HandPosition dataclass）
- [x] src/models/calibration_config.py を実装（CalibrationConfig dataclass）
- [x] src/models/cleaning_session.py を実装（CleaningSession dataclass）

## フェーズ3: ビジネスロジック

- [x] src/tracking/__init__.py を作成
- [x] src/tracking/grid_tracker.py を実装（GridTracker: 累積時間・清掃完了判定）

## フェーズ4: データ永続化

- [x] src/storage/__init__.py を作成
- [x] src/storage/data_storage.py を実装（DataStorage: JSON保存・読み込み）

## フェーズ5: 入力レイヤー

- [x] src/input/__init__.py を作成
- [x] src/input/camera_manager.py を実装（CameraManager: カメラ取得・再接続）

## フェーズ6: 検出レイヤー

- [x] src/detection/__init__.py を作成
- [x] src/detection/calibration_manager.py を実装（CalibrationManager: マウスUI・ホモグラフィ）
- [x] src/detection/hand_detector.py を実装（HandDetector: MediaPipe手検出）

## フェーズ7: 出力レイヤー

- [x] src/output/__init__.py を作成
- [x] src/output/heatmap_renderer.py を実装（HeatmapRenderer: 3色ヒートマップ）
- [x] src/output/display_controller.py を実装（DisplayController: 統合表示・アラート）

## フェーズ8: エントリーポイント

- [x] src/main.py を実装（メインループ・コンポーネント統合）

## フェーズ9: テスト

- [x] tests/ ディレクトリ構造を作成
- [x] tests/unit/tracking/test_grid_tracker.py を実装
- [x] tests/unit/detection/test_calibration_manager.py を実装
- [x] tests/unit/storage/test_data_storage.py を実装
- [ ] pytest を実行して全テストパスを確認

## 実装後の振り返り

（実装完了後に記入）
