"""
equipment_state_consumer.py — 設備狀態 Consumer 模組

處理 Status category 的 payload，進行狀態碼標準化和轉移驗證。
支援：
  - 設備原始狀態字串 → E10 標準狀態碼的 mapping
  - 狀態轉移驗證（非法轉移告警）
  - 每台設備的當前狀態快取（OEE 計算用）
  - 可自訂的 mapping 規則（不同設備廠牌不同）

用法（整合到 consumer_example.py）：

    from equipment_state_consumer import EquipmentStateManager

    state_mgr = EquipmentStateManager(db_conn)

    # on_message callback 中
    if category == "Status":
        state_mgr.process_status(topic, msg)

依賴套件：
    pip install psycopg2-binary pyyaml
"""

import json
import logging
from datetime import datetime
from typing import Optional

import psycopg2

logger = logging.getLogger("uns_consumer.equipment_state")


# ═══════════════════════════════════════════════════════════════
# 狀態碼定義
# ═══════════════════════════════════════════════════════════════

# E10 簡化版狀態枚舉
STATE_CODES = {
    # PRODUCTIVE
    "running":            100,
    "loading_unloading":  101,
    # STANDBY
    "idle":               200,
    "setup_changeover":   201,
    "warmup":             202,
    "waiting_material":   203,
    "waiting_operator":   204,
    # DOWN
    "planned_maintenance":300,
    "unplanned_down":     301,
    "repair":             302,
    "calibration":        303,
    # NON_SCHEDULED
    "non_scheduled":      400,
    "holiday":            401,
    "engineering":        402,
}

STATE_CATEGORIES = {
    100: "productive", 101: "productive",
    200: "standby", 201: "standby", 202: "standby",
    203: "standby", 204: "standby",
    300: "down", 301: "down", 302: "down", 303: "down",
    400: "non_scheduled", 401: "non_scheduled", 402: "non_scheduled",
}

# 合法的狀態轉移
VALID_TRANSITIONS = {
    "running":            {"loading_unloading", "idle", "setup_changeover", "unplanned_down", "planned_maintenance"},
    "loading_unloading":  {"running", "idle"},
    "idle":               {"running", "setup_changeover", "warmup", "planned_maintenance", "non_scheduled", "waiting_material", "waiting_operator"},
    "setup_changeover":   {"warmup", "running", "idle"},
    "warmup":             {"running", "unplanned_down"},
    "waiting_material":   {"running", "idle"},
    "waiting_operator":   {"running", "idle"},
    "planned_maintenance":{"idle", "warmup", "calibration"},
    "unplanned_down":     {"repair"},
    "repair":             {"idle", "warmup", "calibration"},
    "calibration":        {"idle", "warmup"},
    "non_scheduled":      {"idle", "planned_maintenance"},
    "holiday":            {"idle"},
    "engineering":        {"idle", "running"},
}


class EquipmentStateMapper:
    """
    將設備原始狀態字串 mapping 到 E10 標準狀態碼。

    不同廠牌的設備傳不同的狀態字串：
      Siemens PLC: "RUN", "STOP", "FAULT"
      Fanuc CNC:   "MRUN", "MSTOP", "ALARM"
      自訂 Sensor:  "1", "2", "3"

    此 class 用 mapping 表做標準化。
    """

    def __init__(self):
        # 預設 mapping：常見的設備狀態字串 → E10 標準名稱
        self.default_map: dict[str, str] = {
            # 各種 "running" 的變體
            "run": "running", "running": "running", "RUN": "running",
            "producing": "running", "PRODUCING": "running",
            "active": "running", "ACTIVE": "running",
            "mrun": "running", "MRUN": "running",
            "auto": "running", "AUTO": "running",
            "processing": "running",

            # 各種 "idle" 的變體
            "idle": "idle", "IDLE": "idle",
            "standby": "idle", "STANDBY": "idle",
            "ready": "idle", "READY": "idle",
            "waiting": "idle", "WAITING": "idle",
            "stop": "idle", "STOP": "idle",
            "stopped": "idle",

            # 各種 "setup" 的變體
            "setup": "setup_changeover", "SETUP": "setup_changeover",
            "changeover": "setup_changeover",
            "toolchange": "setup_changeover",
            "recipe_change": "setup_changeover",

            # 各種 "down" 的變體
            "down": "unplanned_down", "DOWN": "unplanned_down",
            "fault": "unplanned_down", "FAULT": "unplanned_down",
            "error": "unplanned_down", "ERROR": "unplanned_down",
            "alarm": "unplanned_down", "ALARM": "unplanned_down",
            "breakdown": "unplanned_down",

            # 維修
            "maintenance": "planned_maintenance",
            "pm": "planned_maintenance", "PM": "planned_maintenance",
            "repair": "repair", "REPAIR": "repair",

            # 其他
            "warmup": "warmup", "WARMUP": "warmup",
            "preheat": "warmup",
            "off": "non_scheduled", "OFF": "non_scheduled",
        }

        # 設備 / 廠牌 特定 mapping（覆蓋預設）
        # key = equipment_path 的 prefix 或 pattern
        self.equipment_maps: dict[str, dict[str, str]] = {}

    def add_equipment_mapping(self, equipment_pattern: str,
                               mapping: dict[str, str]):
        """
        為特定設備（或設備類型）新增自訂 mapping。

        Args:
            equipment_pattern: 設備路徑的前綴，如 "TaiwanPrecision/Taoyuan/CNC"
            mapping: 原始狀態 → E10 標準名稱 的 mapping
        """
        self.equipment_maps[equipment_pattern] = mapping

    def map(self, equipment_path: str, raw_state: str) -> tuple[str, int]:
        """
        將原始狀態 mapping 到 (E10_name, state_code)。

        Returns:
            (state_name, state_code)，找不到時回傳 ("idle", 200)。
        """
        # 先查設備特定 mapping
        for pattern, mapping in self.equipment_maps.items():
            if equipment_path.startswith(pattern):
                if raw_state in mapping:
                    name = mapping[raw_state]
                    return name, STATE_CODES.get(name, 200)

        # 回退到預設 mapping
        name = self.default_map.get(raw_state, None)
        if name:
            return name, STATE_CODES.get(name, 200)

        # 完全未知的狀態 → 記 warning，回傳 idle
        logger.warning(
            f"未知的設備狀態: '{raw_state}' @ {equipment_path}，"
            f"mapping 為 idle(200)。請更新 mapping 表。"
        )
        return "idle", 200


class EquipmentStateManager:
    """
    設備狀態管理器：處理 Status payload → 標準化 → 驗證轉移 → 寫入 DB。
    """

    def __init__(self, db_conn, mapper: EquipmentStateMapper = None,
                 metrics=None, strict_transition: bool = False):
        """
        Args:
            db_conn: psycopg2 連線
            mapper: 狀態字串 mapping 器（不傳用預設）
            metrics: ConsumerMetrics 實例
            strict_transition: True = 非法轉移時拒絕寫入；False = 記 warning 但仍寫入
        """
        self.db = db_conn
        self.mapper = mapper or EquipmentStateMapper()
        self.metrics = metrics
        self.strict = strict_transition

        # equipment_path → {"state_name": ..., "state_code": ..., "since": ...}
        self.current_states: dict[str, dict] = {}
        self._load_current_states()

    def _load_current_states(self):
        """啟動時從 DB 載入各設備的最新狀態"""
        cur = self.db.cursor()
        cur.execute(
            """SELECT DISTINCT ON (t.asset_path)
                      t.asset_path, s.state_code, s.time
               FROM ts_status s
               JOIN tags t ON s.tag_id = t.tag_id
               WHERE s.state_code IS NOT NULL
               ORDER BY t.asset_path, s.time DESC"""
        )
        for row in cur.fetchall():
            asset_path, code, time = row
            name = next(
                (k for k, v in STATE_CODES.items() if v == code), "idle"
            )
            self.current_states[asset_path] = {
                "state_name": name,
                "state_code": code,
                "since": time,
            }
        cur.close()
        logger.info(f"已載入 {len(self.current_states)} 台設備的當前狀態")

    def process_status(self, topic: str, msg: dict) -> dict:
        """
        處理一筆 Status payload。

        1. 將原始狀態 mapping 到 E10 標準碼
        2. 驗證狀態轉移是否合法
        3. 更新 ts_status 的 state_code 欄位
        4. 更新內部快取

        Returns:
            {"equipment": ..., "raw_state": ..., "mapped_state": ...,
             "state_code": ..., "transition_valid": ..., "written": ...}
        """
        meta = msg.get("_meta", {})
        data = msg.get("data", {})

        equipment_path = meta.get("source", "")
        timestamp = datetime.fromisoformat(
            meta.get("timestamp", datetime.now().isoformat())
        )

        # 原始狀態（payload 可能直接帶 state_code 或 state_text）
        raw_state = data.get("state_text", "")
        payload_code = data.get("state_code")

        # Mapping
        if payload_code is not None:
            # payload 直接帶了標準 state_code
            state_code = payload_code
            state_name = next(
                (k for k, v in STATE_CODES.items() if v == payload_code),
                raw_state
            )
        else:
            # 需要 mapping
            state_name, state_code = self.mapper.map(equipment_path, raw_state)

        # 驗證狀態轉移
        current = self.current_states.get(equipment_path)
        transition_valid = True

        if current:
            current_name = current["state_name"]
            if current_name == state_name:
                # 同一狀態再報一次，跳過
                return {
                    "equipment": equipment_path,
                    "raw_state": raw_state,
                    "mapped_state": state_name,
                    "state_code": state_code,
                    "transition_valid": True,
                    "written": False,
                    "reason": "same_state"
                }

            allowed = VALID_TRANSITIONS.get(current_name, set())
            if state_name not in allowed:
                transition_valid = False
                logger.warning(
                    f"非法狀態轉移: {equipment_path} "
                    f"{current_name}({current['state_code']}) → "
                    f"{state_name}({state_code})"
                )

                if self.strict:
                    return {
                        "equipment": equipment_path,
                        "raw_state": raw_state,
                        "mapped_state": state_name,
                        "state_code": state_code,
                        "transition_valid": False,
                        "written": False,
                        "reason": "invalid_transition"
                    }

        # 寫入 ts_status（更新 state_code）
        # 注意：這裡假設 consumer_example.py 已經把基本的 ts_status 寫入了，
        # 我們只是補上 state_code。如果你要完全在這裡處理，需要完整 INSERT。
        cur = self.db.cursor()

        # 取得 tag_id
        cur.execute(
            """SELECT tag_id FROM tags
               WHERE asset_path = %s AND category = 'Status' LIMIT 1""",
            (equipment_path,)
        )
        tag_row = cur.fetchone()

        if tag_row:
            tag_id = tag_row[0]
            # 寫入完整的 status record
            cur.execute(
                """INSERT INTO ts_status (time, tag_id, state_text, state_code)
                   VALUES (%s, %s, %s, %s)""",
                (timestamp, tag_id, state_name, state_code)
            )
        else:
            # 建立 tag
            cur.execute(
                """INSERT INTO tags (display_name, asset_path, category, data_point, data_type)
                   VALUES (%s, %s, 'Status', 'MachineState', 'string')
                   RETURNING tag_id""",
                (f"{equipment_path} 狀態", equipment_path)
            )
            tag_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO ts_status (time, tag_id, state_text, state_code)
                   VALUES (%s, %s, %s, %s)""",
                (timestamp, tag_id, state_name, state_code)
            )

        self.db.commit()
        cur.close()

        # 更新快取
        self.current_states[equipment_path] = {
            "state_name": state_name,
            "state_code": state_code,
            "since": timestamp,
        }

        logger.info(
            f"Status: {equipment_path} → {state_name}({state_code}) "
            f"[valid={transition_valid}]"
        )

        return {
            "equipment": equipment_path,
            "raw_state": raw_state,
            "mapped_state": state_name,
            "state_code": state_code,
            "transition_valid": transition_valid,
            "written": True,
        }

    def get_current_state(self, equipment_path: str) -> Optional[dict]:
        """取得某設備的當前狀態"""
        return self.current_states.get(equipment_path)

    def get_all_states(self) -> dict:
        """取得所有設備的當前狀態"""
        return dict(self.current_states)

    def get_state_summary(self) -> dict:
        """
        統計各狀態的設備數量。

        回傳：
            {"productive": 5, "standby": 3, "down": 1, "non_scheduled": 2}
        """
        summary = {"productive": 0, "standby": 0, "down": 0, "non_scheduled": 0}
        for state in self.current_states.values():
            category = STATE_CATEGORIES.get(state["state_code"], "non_scheduled")
            summary[category] += 1
        return summary
