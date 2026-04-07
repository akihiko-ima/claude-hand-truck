"""GridTracker のユニットテスト。"""

import time

import pytest

from src.models.hand_position import HandPosition
from src.tracking.grid_tracker import GridTracker


def make_position(x: float, y: float, camera_id: int = 0) -> HandPosition:
    """テスト用 HandPosition を生成するヘルパー。"""
    return HandPosition(
        x_normalized=x,
        y_normalized=y,
        timestamp=time.time(),
        camera_id=camera_id,
        confidence=1.0,
    )


class TestGridTrackerInit:
    def test_grid_is_2x12_on_init(self) -> None:
        tracker = GridTracker()
        grid = tracker.get_grid()
        assert len(grid) == 2
        assert all(len(row) == 12 for row in grid)

    def test_grid_size_is_configurable(self) -> None:
        tracker = GridTracker(rows=3, cols=6)
        grid = tracker.get_grid()
        assert len(grid) == 3
        assert all(len(row) == 6 for row in grid)

    def test_all_cells_are_not_cleaned_on_init(self) -> None:
        tracker = GridTracker()
        for row in tracker.get_grid():
            for cell in row:
                assert cell.accumulated_seconds == 0.0
                assert cell.is_cleaned is False

    def test_cleaning_rate_is_zero_on_init(self) -> None:
        tracker = GridTracker()
        assert tracker.get_cleaning_rate() == 0.0


class TestGridTrackerUpdate:
    def test_update_with_empty_positions_does_not_increment(self) -> None:
        tracker = GridTracker()
        tracker.update([], delta_time=1.0)
        for row in tracker.get_grid():
            for cell in row:
                assert cell.accumulated_seconds == 0.0

    def test_update_increments_detected_cell(self) -> None:
        tracker = GridTracker()
        pos = make_position(x=0.5, y=0.5)  # col=6, row=1
        tracker.update([pos], delta_time=2.0)
        cell = tracker.get_grid()[1][6]
        assert cell.accumulated_seconds == pytest.approx(2.0)

    def test_update_does_not_increment_undetected_cell(self) -> None:
        tracker = GridTracker()
        pos = make_position(x=0.0, y=0.0)  # col=0, row=0
        tracker.update([pos], delta_time=2.0)
        # col=1, row=0 は更新されないはず
        cell = tracker.get_grid()[0][1]
        assert cell.accumulated_seconds == 0.0

    def test_duplicate_positions_in_same_cell_count_once(self) -> None:
        """同一セルに複数の手座標があっても1回しか加算しない。"""
        tracker = GridTracker()
        pos1 = make_position(x=0.1, y=0.1, camera_id=0)
        pos2 = make_position(x=0.1, y=0.1, camera_id=1)  # 同じセルへの別カメラ
        tracker.update([pos1, pos2], delta_time=1.0)
        cell = tracker.get_grid()[0][1]
        assert cell.accumulated_seconds == pytest.approx(1.0)

    def test_is_cleaned_when_accumulated_5_seconds(self) -> None:
        tracker = GridTracker()
        pos = make_position(x=0.0, y=0.0)  # col=0, row=0
        tracker.update([pos], delta_time=5.0)
        assert tracker.get_grid()[0][0].is_cleaned is True

    def test_is_not_cleaned_when_accumulated_less_than_5_seconds(self) -> None:
        tracker = GridTracker()
        pos = make_position(x=0.0, y=0.0)
        tracker.update([pos], delta_time=4.9)
        assert tracker.get_grid()[0][0].is_cleaned is False

    def test_cleaning_rate_increases_as_cells_cleaned(self) -> None:
        tracker = GridTracker()
        # col=0, row=0 だけ清掃済みにする
        pos = make_position(x=0.0, y=0.0)
        tracker.update([pos], delta_time=5.0)
        assert tracker.get_cleaning_rate() == pytest.approx(1 / 24)

    def test_cleaning_rate_is_1_when_all_cells_cleaned(self) -> None:
        tracker = GridTracker()
        for r in range(2):
            for c in range(12):
                x = (c + 0.5) / 12
                y = (r + 0.5) / 2
                pos = make_position(x=x, y=y)
                tracker.update([pos], delta_time=5.0)
        assert tracker.get_cleaning_rate() == pytest.approx(1.0)


class TestGridTrackerPositionToCell:
    def test_top_left_corner_maps_to_row0_col0(self) -> None:
        tracker = GridTracker()
        pos = make_position(x=0.0, y=0.0)
        row, col = tracker._position_to_cell(pos)
        assert row == 0
        assert col == 0

    def test_bottom_right_corner_maps_to_row1_col11(self) -> None:
        tracker = GridTracker()
        pos = make_position(x=0.999, y=0.999)
        row, col = tracker._position_to_cell(pos)
        assert row == 1
        assert col == 11

    def test_out_of_range_x_is_clamped(self) -> None:
        tracker = GridTracker()
        pos = make_position(x=1.5, y=0.0)
        row, col = tracker._position_to_cell(pos)
        assert col == 11  # 最大値にクランプ

    def test_negative_x_is_clamped(self) -> None:
        tracker = GridTracker()
        pos = make_position(x=-0.5, y=0.0)
        row, col = tracker._position_to_cell(pos)
        assert col == 0  # 0にクランプ

    def test_center_maps_to_correct_cell(self) -> None:
        tracker = GridTracker()
        pos = make_position(x=0.5, y=0.5)
        row, col = tracker._position_to_cell(pos)
        assert row == 1
        assert col == 6


class TestGridTrackerReset:
    def test_reset_clears_accumulated_seconds(self) -> None:
        tracker = GridTracker()
        pos = make_position(x=0.0, y=0.0)
        tracker.update([pos], delta_time=5.0)
        tracker.reset()
        assert tracker.get_grid()[0][0].accumulated_seconds == 0.0
        assert tracker.get_grid()[0][0].is_cleaned is False

    def test_reset_clears_cleaning_rate(self) -> None:
        tracker = GridTracker()
        pos = make_position(x=0.0, y=0.0)
        tracker.update([pos], delta_time=5.0)
        tracker.reset()
        assert tracker.get_cleaning_rate() == 0.0
