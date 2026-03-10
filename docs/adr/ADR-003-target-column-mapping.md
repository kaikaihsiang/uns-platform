# ADR 003: Heterogeneous Payload Integration & Target Column Mapping

## Status
Accepted

## Date
2026-03-05

## Context
The UNS Platform aims to unify data from various L0-L4 systems (SCADA, MES, EAP, etc.). These systems generate highly heterogeneous payloads (e.g., Alarms and Events typically have varying field names like `error_lvl` vs `severity`, or `fault_code` vs `code`). 

### Payload Pattern Analysis
Industrial data payloads (from L0 to L4) fundamentally boil down to five patterns:

1. **Single Scalar (S)**: 1 timestamp → 1 field → 1 scalar value. Typical for SCADA/DCS.
   ```json
   {"tag": "TI-101", "value": 85.5, "quality": "GOOD", "timestamp": "2026-03-05T02:00:00Z"}
   ```
2. **Flat Object (F)**: 1 timestamp → N fields → N scalar values. Typical for MES Events, Alarms, or EAP SV Reports.
   ```json
   {"event_code": "LOT_START", "lot_id": "L001", "operator": "OP-01", "timestamp": "2026-03-05T02:00:00Z"}
   ```
3. **Array/Blob (A)**: 1 timestamp → 1 field → Array of values/Complex Object. Typical for High-frequency Trace Data or FFT Spectrum matrices.
   ```json
   {"sensor_id": "VIB-01", "fft_spectrum": {"freq_hz": [1.0, 2.0], "amplitudes": [0.1, 0.5]}}
   ```
4. **Batch Timeseries (B)**: N timestamps → specific fields/values. Typical for equipment reconnection batch uploads.
   ```json
   {"batch": true, "records": [{"ts": "T1", "temp": 350}, {"ts": "T2", "temp": 351}]}
   ```
5. **Nested Metadata (N)**: 1 timestamp → deep object tree. Typical for L4 ERP Work Orders or Recipes (often non-timeseries Master Data).

Our MVP scope explicitly covers patterns **S**, **F**, and **A** (stored as JSON Blob). 

While ADR-001 defined the use of the `category` field to route data to different TimescaleDB tables (`ts_telemetry`, `ts_status`, `ts_alarms`, `ts_events`, `ts_measurements`), the current Data Engine implementation relies on hardcoded keys (e.g., `payload.get("severity")`) when building records for tables other than `ts_telemetry`. This rigid approach fails to accommodate the variability of the "Flat Object (F)" industrial data payloads described above.

We need a flexible mechanism to extract varying payload fields into standardized database columns without requiring custom code modification in the Data Engine or the Edge gateway per device.

## Decision
We will adopt a **Centralized ETL with Target Column Mapping** approach, augmented by a **Raw Payload Safety Net**:

1. **Dual Storage (Safety Net)**: All incoming messages will continue to be stored in their entirety in `ts_raw_payloads` to ensure no data loss and to support future complex analytical processing (Lambda Architecture).
2. **Schema-Driven Target Column Mapping (Centralized ETL)**: 
   - We will extend the `schema_types` definition. Each `field` definition will now support an optional `target_column` attribute.
   - The UI and API for Schema Management will allow users to specify which extracted field maps to which specific column in the target TimescaleDB table (e.g., mapping `$.error_lvl` to the `severity` column in the `ts_alarms` table).
3. **JSONB `details` Column as a Buffer**:
   - All destination tables (`ts_events`, `ts_alarms`, `ts_measurements`, `ts_status`) must include a `details` (JSONB) column.
   - Any extracted field that does not explicitly map to a standard column (like `code` or `severity`) will be aggregated and stored in this `details` column to preserve context without requiring schema changes.

## Consequences

### Positive
* **High Flexibility**: The platform can ingest practically any flat JSON payload without requiring software updates.
* **No Edge Changes Required**: Device vendors do not need to standardize their payload formats before publishing.
* **Maintainable Data Engine**: The `pipeline.py` and `db_writer.py` logic becomes entirely metadata-driven, relying on the `schema_types` definition rather than hardcoded logic.

### Negative / Risks
* **Increased UI Complexity**: The Frontend must provide an intuitive interface for users to define these mappings during Schema creation.
* **Data Engine Refactoring**: The current `db_writer.py` and `pipeline.py` need significant updates to dynamically route `ExtractedValue`s to specific record attributes or the `details` JSONB object based on the `target_column` configuration.

## Required Actions for MVP
1. **Database Schema Update**: Ensure all non-telemetry tables have a `details` JSONB column. Update the `SchemaType` model to support `target_column`.
2. **Backend API Update**: Allow CRUD operations on `target_column` within schema fields.
3. **Frontend Update**: Add mapping UI in Schema Management for non-telemetry categories.
4. **Data Engine Update**: Refactor `pipeline.py` to use `target_column` and populate the `details` JSONB column dynamically.
