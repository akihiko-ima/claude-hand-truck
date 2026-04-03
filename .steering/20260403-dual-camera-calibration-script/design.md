# 設計書

## アーキテクチャ概要

スタンドアロンスクリプト（`scripts/setup_calibration.py`）として実装する。
既存の `CalibrationManager` / `CalibrationConfig` を再利用し、新たなクラスは作らない。

```
setup_calibration.py
  ├── _calibrate_camera(cam_id, cap) → list[tuple[int,int]]
  │     カメラ映像を表示し、4頂点をクリックで取得
  ├── _build_and_save(cam_id, corners, manager) → CalibrationConfig
  │     CalibrationManager._build_config + save_config を呼ぶ
  └── _show_blend_preview(config0, config1, frame0, frame1)
        両カメラの俯瞰展開をブレンドして表示
```

## コンポーネント設計

### 1. `_calibrate_camera(cam_id, cap)`

**責務**:
- 指定カメラのウィンドウを開く
- マウスクリックで4頂点を取得して返す

**実装の要点**:
- 既存 `CalibrationManager._mouse_callback` と同等のロジックをスクリプト内に実装
- `r` キーでリセット
- 4点収集後にウィンドウを閉じる
- ライブ映像ではなく1枚のキャプチャフレーム上でクリック（静止画）
  - 理由: 点を正確に選ぶには静止フレームが操作しやすい

### 2. `_build_and_save(cam_id, corners, manager)`

**責務**:
- `CalibrationManager._build_config()` でホモグラフィ行列を計算
- `CalibrationManager.save_config()` で JSON 保存

**実装の要点**:
- `_build_config` はアンダースコアメソッドだが同一モジュール内相当の操作なのでスクリプトから直接呼ぶ

### 3. `_show_blend_preview(config0, config1, frame0, frame1)`

**責務**:
- 両カメラ映像をホモグラフィ変換でテーブル俯瞰（正規化）座標に展開
- 2枚の俯瞰ビューを alpha ブレンドして1枚の確認ウィンドウに表示

**実装の要点**:
- 出力サイズ: 幅1200px × 高さ200px（テーブル比 1800:300 = 6:1 に近いサイズ）
- `cv2.warpPerspective` でホモグラフィ適用
  - src_points: CalibrationConfig.table_corners（カメラ座標）
  - dst_points: 出力サイズの4隅
- alpha ブレンド: `cv2.addWeighted(warped0, 0.5, warped1, 0.5, 0)`
- `s` キーで確定、`r` キーでカメラ0から再キャリブレーション

## データフロー

```
1. Camera 0 起動 → フレーム取得（静止）
2. Camera 1 起動 → フレーム取得（静止）
3. _calibrate_camera(0, ...) → corners_0 (4点)
4. _calibrate_camera(1, ...) → corners_1 (4点)
5. CalibrationManager._build_config(0, corners_0) → config_0
6. CalibrationManager._build_config(1, corners_1) → config_1
7. _show_blend_preview(config_0, config_1, frame_0, frame_1)
   → s: save_config(config_0), save_config(config_1) → 終了
   → r: ステップ3に戻る
```

## ディレクトリ構造

```
scripts/
  setup_calibration.py   ← 新規作成
config/
  calibration_0.json     ← 保存先（既存と同じ）
  calibration_1.json     ← 保存先（既存と同じ）
```

## 実装の順序

1. スクリプト骨格とカメラ起動処理
2. `_calibrate_camera` 関数（静止フレーム上でのクリック点収集）
3. `_build_and_save` 関数（CalibrationManager 再利用）
4. `_show_blend_preview` 関数（俯瞰ブレンド表示）
5. メイン処理（フロー制御・リトライ対応）
