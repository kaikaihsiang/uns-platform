"""
Tests for UNS Data Engine — Deadband Filter
"""

from src.deadband import DeadbandFilter


class TestDeadbandFilter:
    """Deadband Filter 測試。"""

    def setup_method(self):
        self.db = DeadbandFilter(enabled=True)

    # ── null deadband → always write ──

    def test_null_deadband_always_writes(self):
        """deadband=None → 每筆都寫。"""
        for _i in range(5):
            assert self.db.should_write(tag_id=1, new_value=25.0, deadband=None)

    # ── 首筆一定寫 ──

    def test_first_value_always_writes(self):
        """第一筆一定寫入（沒有 last_value）。"""
        assert self.db.should_write(tag_id=1, new_value=25.0, deadband=0.1)

    # ── 數值 deadband ──

    def test_same_value_filtered(self):
        """同值連發 → 只有第一筆寫入。"""
        assert self.db.should_write(tag_id=1, new_value=25.0, deadband=0.1)
        assert not self.db.should_write(tag_id=1, new_value=25.0, deadband=0.1)
        assert not self.db.should_write(tag_id=1, new_value=25.0, deadband=0.1)

    def test_small_change_filtered(self):
        """變化 < deadband → 跳過。"""
        assert self.db.should_write(tag_id=1, new_value=25.0, deadband=0.1)
        assert not self.db.should_write(tag_id=1, new_value=25.05, deadband=0.1)
        assert not self.db.should_write(tag_id=1, new_value=25.09, deadband=0.1)

    def test_large_change_passes(self):
        """變化 >= deadband → 寫入。"""
        assert self.db.should_write(tag_id=1, new_value=25.0, deadband=0.1)
        assert self.db.should_write(tag_id=1, new_value=25.2, deadband=0.1)
        assert self.db.should_write(tag_id=1, new_value=24.9, deadband=0.1)

    def test_acceptance_criteria_10_same_values(self):
        """
        驗收標準：同值連發 10 次（deadband=0.1）→ 只寫 1 筆。
        """
        write_count = 0
        for _ in range(10):
            if self.db.should_write(tag_id=1, new_value=25.0, deadband=0.1):
                write_count += 1
        assert write_count == 1

    # ── change_only（字串） ──

    def test_change_only_same_string(self):
        """change_only + 相同字串 → 跳過。"""
        assert self.db.should_write(tag_id=2, new_value="running", deadband="change_only")
        assert not self.db.should_write(tag_id=2, new_value="running", deadband="change_only")

    def test_change_only_different_string(self):
        """change_only + 不同字串 → 寫入。"""
        assert self.db.should_write(tag_id=2, new_value="running", deadband="change_only")
        assert self.db.should_write(tag_id=2, new_value="idle", deadband="change_only")

    # ── 多 tag 獨立 ──

    def test_independent_tag_state(self):
        """不同 tag_id 的 deadband 狀態互不影響。"""
        assert self.db.should_write(tag_id=1, new_value=25.0, deadband=0.1)
        assert self.db.should_write(tag_id=2, new_value=25.0, deadband=0.1)
        assert not self.db.should_write(tag_id=1, new_value=25.0, deadband=0.1)
        assert not self.db.should_write(tag_id=2, new_value=25.0, deadband=0.1)

    # ── disabled ──

    def test_disabled_filter(self):
        """功能關閉 → 全部寫入。"""
        db = DeadbandFilter(enabled=False)
        assert db.should_write(tag_id=1, new_value=25.0, deadband=0.1)
        assert db.should_write(tag_id=1, new_value=25.0, deadband=0.1)

    # ── edge cases ──

    def test_negative_values(self):
        """負值也能正確處理。"""
        assert self.db.should_write(tag_id=3, new_value=-10.0, deadband=0.5)
        assert not self.db.should_write(tag_id=3, new_value=-10.3, deadband=0.5)
        assert self.db.should_write(tag_id=3, new_value=-10.6, deadband=0.5)

    def test_zero_deadband(self):
        """deadband=0 → 任何微小變化都寫。"""
        assert self.db.should_write(tag_id=4, new_value=1.0, deadband=0.0)
        assert self.db.should_write(tag_id=4, new_value=1.0001, deadband=0.0)

    def test_clear(self):
        """clear() 後 state 重置。"""
        assert self.db.should_write(tag_id=1, new_value=25.0, deadband=0.1)
        assert not self.db.should_write(tag_id=1, new_value=25.0, deadband=0.1)
        self.db.clear()
        # 清除後，相同值視為首筆
        assert self.db.should_write(tag_id=1, new_value=25.0, deadband=0.1)

    def test_state_count(self):
        """追蹤的 tag 數量。"""
        assert self.db.state_count == 0
        self.db.should_write(tag_id=1, new_value=25.0, deadband=0.1)
        assert self.db.state_count == 1
        self.db.should_write(tag_id=2, new_value=25.0, deadband=0.1)
        assert self.db.state_count == 2
