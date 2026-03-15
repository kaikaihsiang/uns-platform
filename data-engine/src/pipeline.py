"""
UNS Data Engine — Pipeline Orchestrator

組裝整條 data pipeline：
  MQTT msg → Decoder → Schema Matcher → Persist Decision
                                         ├── passthrough → skip
                                         ├── retain → skip (PoC)
                                         └── db → Field Extractor → Deadband → DB Writer
                                                └── Raw Writer (if store_raw=true)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from .auto_detect import AutoDetector
from .category_router import CategoryRouter
from .config import Config
from .context_cache import ActiveRunCache
from .db_pool import DBPool
from .db_writer import DBWriter
from .deadband import DeadbandFilter
from .decoder import DecodeResult, get_decoder
from .field_extractor import FieldExtractor
from .master_data_cache import MasterDataCache
from .records import (
    AlarmRecord,
    EventRecord,
    MeasurementRecord,
    MetricsRecord,
    RawPayloadRecord,
    StatusRecord,
    TelemetryRecord,
)
from .schema_matcher import SchemaMatcher

logger = logging.getLogger("uns.pipeline")


class TagLookup:
    """
    Tag 查找：MQTT topic + field_name → tag_id。
    """

    def __init__(self, db_pool: Optional[DBPool] = None):
        self._db_pool = db_pool
        # Mapping: "topic::field_name" -> (tag_id, asset_path)
        self._cache: dict[str, tuple[int, str]] = {}
        if db_pool:
            self._load_from_db()

    def _load_from_db(self):
        """載入所有 active mapping，排除已軟刪除的 Tag。"""
        if not self._db_pool:
            return

        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT m.mqtt_topic, m.tag_id, t.asset_path
                    FROM tag_source_mapping m
                    JOIN tags t ON m.tag_id = t.tag_id
                    WHERE m.active = true AND t.deleted_at IS NULL
                    """
                )
                for row in cur.fetchall():
                    self._cache[row[0]] = (row[1], row[2])
                cur.close()
            logger.info("Tag cache loaded: %d active mappings", len(self._cache))
        except Exception as e:
            logger.error(f"Failed to load tag cache: {e}")

    def get_tag_id(
        self,
        topic: str,
        field_name: str,
        asset_path: Optional[str] = None,
        unit: Optional[str] = None,
        data_type: str = "float",
        schema_category: str = "Telemetry",
    ) -> tuple[int, str]:
        """查找或建立 tag_id。"""
        key = f"{topic}::{field_name}" if field_name else topic

        if key in self._cache:
            return self._cache[key]

        target_asset_path = asset_path or topic

        if not self._db_pool:
            fake_id = abs(hash(key)) % 1_000_000
            self._cache[key] = (fake_id, target_asset_path)
            return (fake_id, target_asset_path)

        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT m.tag_id, t.asset_path
                    FROM tag_source_mapping m
                    JOIN tags t ON m.tag_id = t.tag_id
                    WHERE m.mqtt_topic = %s AND m.active = true AND t.deleted_at IS NULL
                    """,
                    (key,),
                )
                row = cur.fetchone()
                if row:
                    tag_id, asset_path = row[0], row[1]
                    self._cache[key] = (tag_id, asset_path)
                    cur.close()
                    return (tag_id, asset_path)

                display_name = field_name or topic.split("/")[-1]
                db_category = schema_category.capitalize() if schema_category else "Telemetry"

                cur.execute(
                    """INSERT INTO tags (display_name, asset_path, category, data_point, unit, data_type)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       RETURNING tag_id""",
                    (display_name, target_asset_path, db_category, field_name, unit, data_type),
                )
                tag_id = cur.fetchone()[0]

                cur.execute(
                    """INSERT INTO tag_source_mapping (tag_id, mqtt_topic, mapped_by, notes)
                       VALUES (%s, %s, %s, %s)""",
                    (tag_id, key, "data-engine-auto", "Auto-created by Data Engine"),
                )

                conn.commit()
                cur.close()
                self._cache[key] = (tag_id, target_asset_path)
                logger.info("New tag created: %s → tag_id=%d (category: %s)", key, tag_id, db_category)
                return (tag_id, target_asset_path)

        except Exception as e:
            logger.error("Tag lookup/creation failed for %s: %s", key, e)
            raise

    def refresh(self):
        if self._db_pool:
            self._cache.clear()
            self._load_from_db()


class Pipeline:
    def __init__(
        self,
        db_pool: Optional[DBPool] = None,
        schema_matcher: Optional[SchemaMatcher] = None,
        tag_lookup: Optional[TagLookup] = None,
        db_writer: Optional[DBWriter] = None,
        deadband_filter: Optional[DeadbandFilter] = None,
        field_extractor: Optional[FieldExtractor] = None,
        master_data_cache: Optional[MasterDataCache] = None,
        context_cache: Optional[ActiveRunCache] = None,
        bootstrap_until: Optional[datetime] = None,
    ):
        self._db_pool = db_pool
        self._schema_matcher = schema_matcher or SchemaMatcher(db_pool)
        self._tag_lookup = tag_lookup or TagLookup(db_pool)
        self._db_writer = db_writer or (DBWriter(
            db_pool,
            batch_size=Config.BATCH_SIZE,
            batch_interval_sec=Config.BATCH_INTERVAL_SEC,
        ) if db_pool else None)
        self._deadband = deadband_filter or DeadbandFilter(enabled=Config.DEADBAND_ENABLED)
        self._extractor = field_extractor or FieldExtractor()
        self._bootstrap_until = bootstrap_until
        self._context_cache = context_cache or (ActiveRunCache(db_pool) if db_pool else None)
        self._master_data_cache = master_data_cache or (MasterDataCache(db_pool) if db_pool else None)
        self._auto_detector = AutoDetector(threshold=3)
        self._category_router = CategoryRouter()

        self._total_processed = 0
        self._total_skipped = 0
        self._total_passthrough = 0
        self._total_no_schema = 0

    def _get_context(self, asset_path: str) -> Optional[dict]:
        """
        嘗試從當前路徑或父路徑獲取 Active Run Context (Up-leveling)。
        """
        if not self._context_cache:
            return None
        
        # 1. 精準匹配
        ctx = self._context_cache.get_active_run(asset_path)
        if ctx: return ctx
        
        # 2. 向上查找一層 (例如從 .../Status 向上到設備節點)
        parts = asset_path.split("/")
        if len(parts) > 1:
            parent_path = "/".join(parts[:-1])
            ctx = self._context_cache.get_active_run(parent_path)
            if ctx: return ctx
            
        return None

    def process(self, topic: str, payload_bytes: bytes, receive_time: Optional[datetime] = None):
        if receive_time is None:
            receive_time = datetime.now(timezone.utc)

        self._total_processed += 1

        if self._bootstrap_until and receive_time < self._bootstrap_until:
            logger.debug("Bootstrap mode, skipping: %s", topic)
            self._total_skipped += 1
            return

        schema = self._schema_matcher.match(topic)
        
        # Trigger auto-detection if no schema OR if schema exists but has no fields defined
        if schema is None or not schema.fields:
            if schema is None:
                self._total_no_schema += 1
            
            try:
                decoder = get_decoder("json")
                result = decoder.decode(payload_bytes)
                if result.ok and isinstance(result.data, dict):
                    inferred = self._auto_detector.collect_sample(topic, result.data)
                    if inferred:
                        self._save_schema_suggestion(inferred)
            except Exception as e:
                logger.debug(f"Auto-detect decoding failed for {topic}: {e}")
            
            # If schema is completely missing, we must return. 
            if schema is None:
                return

        if schema.persist_mode in ("passthrough", "retain"):
            self._total_passthrough += 1
            return

        decoder = get_decoder(schema.decoder)
        result: DecodeResult = decoder.decode(payload_bytes)
        if not result.ok:
            logger.warning("Decode failed for %s: %s", topic, result.error)
            return

        payload = result.data

        # _extract_context_data 會在下面依據 category 被呼叫

        if schema.store_raw and self._db_writer:
            payload_size = len(payload_bytes) if payload_bytes else 0
            self._db_writer.add_raw_payload(RawPayloadRecord(
                time=receive_time, topic=topic, payload=payload,
                schema_id=schema.schema_id, payload_size=payload_size
            ))

        schema_category = self._category_router.resolve(schema)
        extracted_values = self._extractor.extract(payload, schema, receive_time)
        logger.debug("Extracted %d values for category %s on topic %s", len(extracted_values), schema_category, topic)

        if schema_category == 'telemetry':
            for ev in extracted_values:
                if not ev.persist: continue
                tag_id, asset_path = self._tag_lookup.get_tag_id(topic=topic, field_name=ev.tag_suffix, unit=ev.unit, data_type=ev.field_type, schema_category=schema_category)
                if tag_id is None: continue
                if not self._deadband.should_write(tag_id, ev.value if ev.value is not None else ev.value_text, ev.deadband): continue
                
                ctx = self._get_context(asset_path)
                run_id = ctx['run_id'] if ctx else None
                lot_id = ctx['lot_id'] if ctx else None
                
                
                context_data = self._extract_context_data(schema_category, payload, ctx, None)
                if self._db_writer:
                    record = TelemetryRecord(time=ev.timestamp, tag_id=tag_id, value=ev.value, value_text=ev.value_text, value_json=ev.value_json, quality='good', run_id=run_id, lot_id=lot_id, context_data=context_data)
                    self._add_to_writer(schema_category, record, asset_path)
        else:
            category_dtype = "string"
            if schema_category == "metrics":
                category_dtype = "json"
            elif schema_category == "measurement":
                category_dtype = "float"

            tag_id, asset_path = self._tag_lookup.get_tag_id(
                topic=topic, 
                field_name="", 
                schema_category=schema_category,
                data_type=category_dtype
            )
            if tag_id is None:
                self._total_skipped += 1
                return
            
            ctx = self._get_context(asset_path)
            run_id = ctx['run_id'] if ctx else None
            lot_id = ctx['lot_id'] if ctx else None

            target_kwargs, details = {}, {}
            for ev in extracted_values:
                val = ev.value if ev.value is not None else (ev.value_text if ev.value_text is not None else ev.value_json)
                if ev.target_column and ev.target_column != "details":
                    target_kwargs[ev.target_column] = val
                if ev.overflow:
                    details[ev.tag_suffix] = val
            
            if not target_kwargs and not details:
                logger.debug("No target fields or details extracted for %s, skipping", topic)
                return
            
            if self._db_writer:
                if schema_category == "metrics":
                    metrics_vals = target_kwargs.get("values") or details
                    record = self._build_non_telemetry_record(schema_category, receive_time, tag_id, target_kwargs, details, run_id, lot_id, schema, asset_path, metrics_vals, payload)
                else:
                    record = self._build_non_telemetry_record(schema_category, receive_time, tag_id, target_kwargs, details, run_id, lot_id, schema, asset_path, payload_meta=payload)
                if record:
                    self._add_to_writer(schema_category, record, asset_path)

    def _build_non_telemetry_record(self, schema_category: str, receive_time: datetime, tag_id: int, target_kwargs: dict, details: dict, run_id: Optional[int] = None, lot_id: Optional[str] = None, schema: Any = None, asset_path: str = "", metrics_values: Optional[dict] = None, payload_meta: Optional[dict] = None):
        import hashlib
        def _generate_synthetic_id(prefix: str, seed_data: str) -> str:
            h = hashlib.sha256(seed_data.encode()).hexdigest()[:8].upper()
            return f"{prefix}-{h}"
        def _safe_float(val, default=None):
            if val is None: return default
            try: return float(val)
            except Exception: return default
        def _safe_str(val, default=""):
            if val is None: return default
            return str(val)

        main_code = _safe_str(target_kwargs.get("state_code") or target_kwargs.get("alarm_code") or target_kwargs.get("event_code") or target_kwargs.get("metric_code"))
        sub_code = _safe_str(target_kwargs.get("sub_state_code") or target_kwargs.get("sub_alarm_code") or target_kwargs.get("sub_event_code") or target_kwargs.get("sub_metric_code"))
        provided_cat = _safe_str(target_kwargs.get("code_category") or target_kwargs.get("metric_category"))

        discovered = self._master_data_cache.find_metadata(main_code, sub_code) if (main_code or sub_code) and self._master_data_cache else None
        final_cat = provided_cat or (discovered["code_category"] if discovered else None)
        final_sub = sub_code or (discovered["sub_code"] if discovered else None)

        context_data = self._extract_context_data(schema_category, payload_meta or {}, None, discovered)

        effective_lot_id = _safe_str(target_kwargs.get("lot_id")) if "lot_id" in target_kwargs else lot_id
        effective_run_id = target_kwargs.get("run_id") if "run_id" in target_kwargs else run_id

        if schema_category == "status":
            return StatusRecord(time=receive_time, tag_id=tag_id, state_code=main_code or "STATE-CODE-UNKNOWN", sub_state_code=final_sub, code_category=final_cat or "equipment_state", mode=target_kwargs.get("mode"), run_id=effective_run_id, lot_id=effective_lot_id, details=details if details else None, context_data=context_data)
        elif schema_category == "alarm":
            alarm_id = target_kwargs.get("alarm_id") or details.get("alarm_id")
            if not alarm_id:
                alarm_id = _generate_synthetic_id("ALM", f"{tag_id}-{main_code}-{receive_time.isoformat()}")
            return AlarmRecord(time=receive_time, tag_id=tag_id, alarm_id=alarm_id, alarm_code=main_code or "ALM-CODE-UNKNOWN", sub_alarm_code=final_sub, code_category=final_cat or "alarm_code", severity=_safe_str(target_kwargs.get("severity"), context_data.get("severity", "warning")), message=_safe_str(target_kwargs.get("message")), alarm_status=_safe_str(target_kwargs.get("alarm_status")), value=_safe_float(target_kwargs.get("value")), threshold=_safe_float(target_kwargs.get("threshold")), run_id=effective_run_id, lot_id=effective_lot_id, details=details if details else None, context_data=context_data)
        elif schema_category == "event":
            trigger = context_data.get("lifecycle_trigger")
            if trigger: self._dispatch_mes_event(trigger, target_kwargs, details, asset_path)
            event_id = target_kwargs.get("event_id") or details.get("event_id")
            if not event_id:
                event_id = _generate_synthetic_id("EVT", f"{tag_id}-{main_code}-{receive_time.isoformat()}")
            return EventRecord(time=receive_time, tag_id=tag_id, event_id=event_id, event_code=main_code or "EVENT-CODE-UNKNOWN", sub_event_code=final_sub, code_category=final_cat or "equipment_state", result=_safe_str(target_kwargs.get("result")), run_id=effective_run_id, lot_id=effective_lot_id, details=details if details else None, context_data=context_data)
        elif schema_category == "measurement":
            return MeasurementRecord(time=receive_time, tag_id=tag_id, value=_safe_float(target_kwargs.get("value"), 0.0), spec_upper=_safe_float(target_kwargs.get("spec_upper")), spec_lower=_safe_float(target_kwargs.get("spec_lower")), target_value=_safe_float(target_kwargs.get("target_value")), result=_safe_str(target_kwargs.get("result")), run_id=effective_run_id, lot_id=effective_lot_id, step_id=_safe_str(target_kwargs.get("step_id")), sample_id=_safe_str(target_kwargs.get("sample_id") or target_kwargs.get("panel_id")), sample_position=_safe_str(target_kwargs.get("sample_position")), inspector=_safe_str(target_kwargs.get("inspector")), context=None, details=details if details else None, context_data=context_data)
        elif schema_category == "metrics":
            return MetricsRecord(time=receive_time, tag_id=tag_id, metric_category=final_cat or "metric_definition", metric_code=main_code or "METRIC-CODE-UNKNOWN", sub_metric_code=final_sub, period=_safe_str(target_kwargs.get("period")), values=target_kwargs.get("values") or metrics_values or {}, run_id=effective_run_id, lot_id=effective_lot_id, context=None, details=details if details else None, context_data=context_data)

    def _add_to_writer(self, schema_category: str, record: Any, asset_path: str):
        # The record's metadata should be populated by the source or by _build_non_telemetry_record
        if schema_category == "telemetry": self._db_writer.add_telemetry(record)
        elif schema_category == "status": self._db_writer.add_status(record)
        elif schema_category == "alarm": self._db_writer.add_alarm(record)
        elif schema_category == "event": self._db_writer.add_event(record)
        elif schema_category == "measurement": self._db_writer.add_measurement(record)
        elif schema_category == "metrics": self._db_writer.add_metrics(record)

    def _extract_context_data(self, schema_category: str, payload: dict, ctx: Optional[dict], discovered: Optional[dict]) -> dict:
        """根據 schema_category 從 payload, context cache 以及 master data 提取 context_data。"""
        context_data = {}
        
        meta_block = payload.get("_meta") or payload.get("metadata") or {}
        if not isinstance(meta_block, dict):
            meta_block = {}

        data_block = payload.get("data") or payload
        if not isinstance(data_block, dict):
            data_block = {}

        def _get_val(*keys):
            for k in keys:
                if k in data_block: return data_block[k]
                if "data" in payload and isinstance(payload["data"], dict) and k in payload["data"]: return payload["data"][k]
                if k in meta_block: return meta_block[k]
            return None

        if schema_category == "telemetry":
            for k in ["usl", "lsl", "target"]:
                val = _get_val(k)
                if val is not None: context_data[k] = val
        elif schema_category == "status":
            for k in ["next_state", "next_mode"]:
                val = _get_val(k)
                if val is not None: context_data[k] = val
        elif schema_category == "alarm":
            for k in ["acknowledge_by", "suggestion"]:
                val = _get_val(k)
                if val is not None: context_data[k] = val
            if discovered:
                disc_meta = discovered.get("metadata") or {}
                if "suggestion" in disc_meta:
                    context_data.setdefault("suggestion", disc_meta["suggestion"])
        elif schema_category == "event":
            for k in ["source_system", "correlation_id"]:
                val = _get_val(k)
                if val is not None: context_data[k] = val
        elif schema_category == "metrics":
            for k in ["weight", "target"]:
                val = _get_val(k)
                if val is not None: context_data[k] = val
            if discovered:
                disc_meta = discovered.get("metadata") or {}
                for k in ["weight", "target"]:
                    if k in disc_meta:
                        context_data.setdefault(k, disc_meta[k])
        elif schema_category == "measurement":
            for k in ["instrument_id", "inspector"]:
                val = _get_val(k)
                if val is not None: context_data[k] = val

        if "lifecycle_trigger" in meta_block:
            context_data["lifecycle_trigger"] = meta_block["lifecycle_trigger"]
        elif discovered:
             disc_meta = discovered.get("metadata") or {}
             if "lifecycle_trigger" in disc_meta:
                 context_data["lifecycle_trigger"] = disc_meta["lifecycle_trigger"]

        return context_data

    def _dispatch_mes_event(self, trigger_type: str, target_kwargs: dict, details: dict, asset_path: str):
        api_url = "http://localhost:8000/api/v1/production-runs"
        temp_path = asset_path
        suffix_lower = temp_path.split("/")[-1].lower() if "/" in temp_path else ""
        if suffix_lower in ("events", "telemetry", "status", "alarms", "measurements", "metrics"):
            equipment_path = "/".join(temp_path.split("/")[:-1])
        else:
            equipment_path = temp_path
        
        equipment_path = "/".join(equipment_path.split("/")[:-1])

        async def _call_api():
            try:
                if trigger_type == "start":
                    payload = {"equipment_path": equipment_path, "lot_id": target_kwargs.get("lot_id") or details.get("lot_id", "UNKNOWN_LOT"), "step_id": target_kwargs.get("step_id") or details.get("step_id", "UNKNOWN_STEP"), "recipe_id": target_kwargs.get("recipe_id") or details.get("recipe_id"), "product_id": target_kwargs.get("product_id") or details.get("product_id"), "context": details if details else {}}
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(api_url + "/", json=payload, timeout=5.0)
                        resp.raise_for_status()
                elif trigger_type == "end":
                    if self._context_cache:
                        ctx = self._context_cache.get_active_run(equipment_path)
                        if ctx and ctx.get("run_id"):
                            run_id = ctx["run_id"]
                            payload = {"status": "Completed", "context": details if details else {}}
                            async with httpx.AsyncClient() as client:
                                resp = await client.patch(f"{api_url}/{run_id}", json=payload, timeout=5.0)
                                resp.raise_for_status()
                if self._context_cache: self._context_cache.refresh(force=True)
            except Exception as e: logger.error(f"Failed to dispatch lifecycle event {trigger_type} to backend: {e}")
        asyncio.create_task(_call_api())

    def _save_schema_suggestion(self, inferred_schema: Dict[str, Any]):
        if not self._db_pool: return
        try:
            with self._db_pool.connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT schema_id FROM uns_payload_schemas WHERE topic_pattern = %s OR schema_name = %s", (inferred_schema["topic_pattern"], inferred_schema["name"]))
                if cur.fetchone():
                    return
                fields_json = json.dumps(inferred_schema["definition"])
                cur.execute(
                    "INSERT INTO uns_payload_schemas (schema_name, fields, topic_pattern, is_suggested, status) VALUES (%s, %s, %s, %s, %s)",
                    (inferred_schema["name"], fields_json, inferred_schema["topic_pattern"], True, "suggested")
                )
                conn.commit()
            if self._schema_matcher:
                self._schema_matcher.refresh(force=True)
        except Exception as e: 
            logger.error(f"❌ [AutoDetect] Failed to save schema suggestion: {e}")

    def flush(self):
        if self._db_writer: self._db_writer.flush()
        if self._context_cache: self._context_cache.refresh()
        if self._master_data_cache: self._master_data_cache.refresh()
        if self._schema_matcher: self._schema_matcher.refresh()

    def close(self):
        if self._db_writer: self._db_writer.close()

    @property
    def stats(self) -> dict:
        result = {"total_processed": self._total_processed, "total_skipped": self._total_skipped, "total_passthrough": self._total_passthrough, "total_no_schema": self._total_no_schema, "deadband_tracked_tags": self._deadband.state_count}
        if self._db_writer: result["db_writer"] = self._db_writer.stats
        return result
