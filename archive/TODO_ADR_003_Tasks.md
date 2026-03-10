# Implementation Tasks: Target Column Mapping (ADR-003)

## Phase 1: Database & Backend Foundation (Backend Agent / DB Schema Engineer)
- [x] **DB Schema Update**: Verify/Add `details` JSONB column to `ts_status`, `ts_alarms`, `ts_events`, `ts_measurements`, `ts_metrics`.
- [x] **Pydantic Model Update**: Update `SchemaTypeCreate`, `SchemaTypeUpdate`, and `SchemaTypeOut` in `backend/app/schemas/__init__.py` to support the `target_column` field inside the `fields` list definition.
- [x] **DB Model Verification**: Ensure that the `schema_types.fields` JSONB column can correctly save and retrieve the new `target_column` attribute.

## Phase 2: Data Engine Refactoring (Data Engine Agent)
- [ ] **FieldExtract Update**: Update `FieldDef` class in `schema_matcher.py` to parse `target_column` from the schema.
- [ ] **ExtractedValue Update**: Update `ExtractedValue` in `field_extractor.py` to carry the `target_column` information.
- [ ] **Pipeline Dynamic Mapping**: Refactor `_build_record` in `pipeline.py`. 
    - Stop using hardcoded keys like `payload.get("severity")`.
    - Loop through extracted values, use `target_column` to assign values to specific properties of `AlarmRecord`, `EventRecord`, etc.
    - If `target_column` is null and category is NOT telemetry, aggregate these values into a dictionary and assign them to the `details` attribute.

## Phase 3: Frontend UI Alignment (Frontend Agent)
- [ ] **Type Definitions**: Update `src/types/namespace.ts` to include `target_column?: string` inside the `fields` array definitions.
- [ ] **Schema Form Update**: In `SchemaForm.tsx` (or similar), when the Category is NOT `telemetry`, show an additional input column/dropdown for `Target Column` in the Fields table.
    - Example: If Category == "alarm", provide dropdown options: `alarm_id`, `code`, `severity`, `message`, `state`, `value`, `threshold`, `details`.
- [ ] **Data Engine E2E Verification**: Write an E2E test script (`run_e2e_target_column.py`) to simulate publishing an Alarm with custom keys (`error_lvl`, `fault_code`) and verify it lands correctly in `ts_alarms` with `details` populated.
