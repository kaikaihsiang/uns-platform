    def _build_non_telemetry_record(self, schema_category: str, record_time: datetime, tag_id: int, target_kwargs: dict, details: dict, run_id: Optional[int] = None, lot_id: Optional[str] = None, schema: Any = None):
        """依據 schema_category + target_column kwargs 組裝對應呈現的 Record 物件。"""
        import hashlib

        def _generate_synthetic_id(prefix: str, seed_data: str) -> str:
            """生成確定性的合成 ID (Prefix + 8位 Hash)。"""
            h = hashlib.sha256(seed_data.encode()).hexdigest()[:8].upper()
            return f"{prefix}-{h}"

        def _safe_float(val, default=None):
            if val is None: return default
            try: return float(val)
            except (ValueError, TypeError): return default

        def _safe_int(val, default=None):
            if val is None: return default
            try: return int(float(val))
            except (ValueError, TypeError): return default

        def _safe_str(val, default=""):
            if val is None: return default
            return str(val)

        if schema_category == "status":
            state = _safe_str(target_kwargs.get("state_code"))
            sub_state = _safe_str(target_kwargs.get("sub_state_code"))
            code_cat = _safe_str(target_kwargs.get("code_category"))

            # [GENERIC ENRICHMENT] Lookup by state_code
            if not code_cat or not sub_state:
                found = self._master_data_cache.find_by_code(state)
                if found:
                    code_cat = code_cat or found["code_category"]
                    sub_state = sub_state or found["sub_code"]
            
            return StatusRecord(
                time=record_time, tag_id=tag_id,
                state_code=state,
                sub_state_code=sub_state if sub_state else None,
                code_category=code_cat or "equipment_state",
                mode=target_kwargs.get("mode"),
                run_id=run_id, lot_id=lot_id,
                details=details if details else None
            )
        elif schema_category == "alarm":
            code = _safe_str(target_kwargs.get("alarm_code", "ALM-AUTO"), "ALM-AUTO")
            sub_code = _safe_str(target_kwargs.get("sub_alarm_code"))
            code_cat = _safe_str(target_kwargs.get("code_category"))

            # [GENERIC ENRICHMENT] Lookup by alarm_code
            if not code_cat or not sub_code:
                found = self._master_data_cache.find_by_code(code)
                if found:
                    code_cat = code_cat or found["code_category"]
                    sub_code = sub_code or found["sub_code"]

            # ID Resolution: target_column > details > synthetic
            alarm_id = target_kwargs.get("alarm_id") or details.get("alarm_id")
            if not alarm_id:
                alarm_id = _generate_synthetic_id("ALM", f"{tag_id}-{code}-{record_time.isoformat()}")

            return AlarmRecord(
                time=record_time, tag_id=tag_id,
                alarm_id=alarm_id,
                alarm_code=code,
                sub_alarm_code=sub_code if sub_code else None,
                code_category=code_cat or "alarm_code",
                severity=_safe_str(target_kwargs.get("severity", "warning"), "warning"),
                message=_safe_str(target_kwargs.get("message")),
                alarm_status=_safe_str(target_kwargs.get("alarm_status", "active"), "active"),
                value=_safe_float(target_kwargs.get("value")),
                threshold=_safe_float(target_kwargs.get("threshold")),
                run_id=run_id, lot_id=lot_id,
                details=details if details else None
            )
        elif schema_category == "event":
            event = _safe_str(target_kwargs.get("event_code", "auto"), "auto")
            sub_event = _safe_str(target_kwargs.get("sub_event_code"))
            code_cat = _safe_str(target_kwargs.get("code_category"))

            # [GENERIC ENRICHMENT] Lookup by event_code
            if not code_cat or not sub_event:
                found = self._master_data_cache.find_by_code(event)
                if found:
                    # Specific for events: we want to find if this is a lifecycle trigger
                    code_cat = code_cat or found["code_category"]
                    sub_event = sub_event or found["sub_code"]
                    
                    # Component 3: MES Event Consumer Hook (Metadata-driven)
                    metadata = found.get("metadata", {})
                    trigger = metadata.get("lifecycle_trigger")
                    if trigger:
                        self._dispatch_mes_event(trigger, target_kwargs, details, asset_path)

            # ID Resolution: target_column > details > synthetic
            event_id = target_kwargs.get("event_id") or details.get("event_id")
            if not event_id:
                event_id = _generate_synthetic_id("EVT", f"{tag_id}-{event}-{record_time.isoformat()}")

            return EventRecord(
                time=record_time, tag_id=tag_id,
                event_id=event_id,
                event_code=event,
                sub_event_code=sub_event if sub_event else None,
                code_category=code_cat or "equipment_state",
                result=_safe_str(target_kwargs.get("result")),
                run_id=run_id,
                lot_id=_safe_str(target_kwargs.get("lot_id")) if "lot_id" in target_kwargs else lot_id,
                details=details if details else None
            )

        elif schema_category == "measurement":
            return MeasurementRecord(
                time=record_time, tag_id=tag_id,
                value=_safe_float(target_kwargs.get("value"), 0.0),
                spec_upper=_safe_float(target_kwargs.get("spec_upper")),
                spec_lower=_safe_float(target_kwargs.get("spec_lower")),
                target_value=_safe_float(target_kwargs.get("target_value")),
                result=_safe_str(target_kwargs.get("result", "pass"), "pass"),
                run_id=run_id,
                lot_id=_safe_str(target_kwargs.get("lot_id")) if "lot_id" in target_kwargs else lot_id,
                step_id=_safe_str(target_kwargs.get("step_id")),
                sample_id=_safe_str(target_kwargs.get("sample_id") or target_kwargs.get("panel_id")),
                sample_position=_safe_str(target_kwargs.get("sample_position")),
                inspector=_safe_str(target_kwargs.get("inspector")),
                context=target_kwargs.get("context"),
                details=details if details else None
            )
        elif schema_category == "metrics":
            m_cat = _safe_str(target_kwargs.get("metric_category"))
            m_code = _safe_str(target_kwargs.get("metric_code") or target_kwargs.get("metric_code"), "UNKNOWN")
            m_sub = _safe_str(target_kwargs.get("sub_metric_code"))
            
            # [GENERIC ENRICHMENT] Lookup by metric_code
            if not m_cat:
                found = self._master_data_cache.find_by_code(m_code)
                if found:
                    m_cat = found["code_category"]
                    m_sub = m_sub or found["sub_code"]

            return MetricsRecord(
                time=record_time, tag_id=tag_id,
                metric_category=m_cat or "metric_definition",
                metric_code=m_code,
                sub_metric_code=m_sub if m_sub else None,
                period=_safe_str(target_kwargs.get("period")),
                values=target_kwargs.get("values") or details,
                context=target_kwargs.get("context"),
                details=details if details else None
            )
