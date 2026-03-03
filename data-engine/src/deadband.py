"""
UNS Data Engine — Deadband Filter

In-memory deadband 過濾：只有值變化量超過門檻才寫入 DB。
減少高頻但低變化量的感測資料寫入，節省儲存成本。

支援：
  - 數值型 deadband：abs(new - old) >= threshold → 寫入
  - "change_only"：值完全沒變 → 跳過（適合字串 / boolean）
  - None/null：不做 deadband，每筆都寫
  - 首筆一定寫（沒有 last_value 時）
"""

import logging
from typing import Optional, Union

logger = logging.getLogger("uns.deadband")

# deadband 設定型別：None（不做）、float（數值門檻）、"change_only"（字串/bool 比對）
DeadbandConfig = Optional[Union[float, str]]


class DeadbandFilter:
    """
    In-memory deadband state manager.

    {tag_id: last_persisted_value}
    """

    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._state: dict[int, object] = {}  # tag_id → last persisted value

    def should_write(
        self,
        tag_id: int,
        new_value: object,
        deadband: DeadbandConfig = None,
    ) -> bool:
        """
        判斷是否應該寫入 DB。

        Args:
            tag_id: Tag ID
            new_value: 新的值（float, str, etc.）
            deadband: deadband 設定（None / float / "change_only"）

        Returns:
            True = 應該寫入, False = 跳過
        """
        # deadband 功能關閉 → 全部寫入
        if not self._enabled:
            return True

        # 沒設定 deadband → 全部寫入
        if deadband is None:
            return True

        # 首筆一定寫入（沒有 last_value）
        if tag_id not in self._state:
            self._state[tag_id] = new_value
            return True

        last_value = self._state[tag_id]

        if deadband == "change_only":
            # 值完全相同 → 跳過
            if new_value == last_value:
                return False
            self._state[tag_id] = new_value
            return True

        if isinstance(deadband, (int, float)):
            # 數值比較
            try:
                diff = abs(float(new_value) - float(last_value))
                if diff < deadband:
                    return False
                self._state[tag_id] = new_value
                return True
            except (TypeError, ValueError):
                # 無法比較 → 寫入（安全起見）
                self._state[tag_id] = new_value
                return True

        # 未知 deadband 型別 → 寫入
        logger.warning("Unknown deadband config type: %r", deadband)
        return True

    def update_state(self, tag_id: int, value: object):
        """手動更新 tag 的 last persisted value（用於初始化等）。"""
        self._state[tag_id] = value

    def clear(self):
        """清除所有 deadband 狀態。"""
        self._state.clear()

    @property
    def state_count(self) -> int:
        """目前追蹤的 tag 數量。"""
        return len(self._state)
