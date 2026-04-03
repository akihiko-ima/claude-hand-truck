# 実装設計 (Design)

## 実装方針

functional-design.md のコンポーネント設計・インターフェース定義に忠実に従う。
依存関係は repository-structure.md の定義通りに閉じる。

## 実装順序

依存関係が少ない順に実装する:

1. `pyproject.toml` - 依存関係定義（最初に必要）
2. `src/models/` - データモデル（全レイヤーの基盤）
3. `src/tracking/grid_tracker.py` - 外部依存なし・テスト容易
4. `src/storage/data_storage.py` - モデルのみ依存
5. `src/input/camera_manager.py` - OpenCVのみ依存
6. `src/detection/calibration_manager.py` - OpenCV + NumPy
7. `src/detection/hand_detector.py` - MediaPipe + CalibrationManager
8. `src/output/heatmap_renderer.py` - OpenCV + NumPy
9. `src/output/display_controller.py` - OpenCV
10. `src/main.py` - 全コンポーネント統合
11. `tests/` - ユニットテスト・統合テスト

## ディレクトリ構成（実装後）

```
src/
├── main.py
├── models/
│   ├── __init__.py
│   ├── grid_cell.py
│   ├── hand_position.py
│   ├── calibration_config.py
│   └── cleaning_session.py
├── input/
│   ├── __init__.py
│   └── camera_manager.py
├── detection/
│   ├── __init__.py
│   ├── calibration_manager.py
│   └── hand_detector.py
├── tracking/
│   ├── __init__.py
│   └── grid_tracker.py
├── output/
│   ├── __init__.py
│   ├── heatmap_renderer.py
│   └── display_controller.py
└── storage/
    ├── __init__.py
    └── data_storage.py

tests/
├── unit/
│   ├── tracking/
│   │   └── test_grid_tracker.py
│   ├── detection/
│   │   └── test_calibration_manager.py
│   └── storage/
│       └── test_data_storage.py
└── integration/
    └── fixtures/
        └── calibration_0.json
```
