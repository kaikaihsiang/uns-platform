---
name: timescaledb-schema
description: >
  TimescaleDB schema design for UNS time-series data. Triggers on tasks
  involving database schema, hypertable creation, retention policies,
  compression, data migration, or query optimization for time-series data.
---

# TimescaleDB Schema Design

## Core Tables

| Table | Purpose | Hypertable? |
|---|---|---|
| `namespace_nodes` | Namespace tree structure | No |
| `tags` | Permanent tag identity (tag_id) | No |
| `tag_source_mapping` | MQTT topic → tag_id mapping | No |
| `schema_types` | Payload structure definitions | No |
| `ts_telemetry` | Time-series sensor data | **Yes** |
| `ts_status` | Equipment state changes | **Yes** |
| `ts_events` | Production/maintenance events | **Yes** |
| `ts_measurements` | Quality measurements (SPC) | **Yes** |
| `ts_raw_payloads` | Raw MQTT payloads for backfill | **Yes** |
| `production_run` | Lot/Step/Recipe context | No |

## Design Patterns

1. **EAV Model** — Each tag value is one row in `ts_telemetry` (not one column per tag)
2. **Hypertable chunk interval** — Default 1 day for high-frequency, 1 week for events
3. **Compression** — Enable after 7 days, segmentby tag_id, orderby time
4. **Retention** — Configurable per-topic via `namespace_nodes.retention_days`
5. **Dual Storage** — Raw payload + extracted values stored simultaneously

## Key Constraints

- `ts_telemetry` PK: `(tag_id, time)` — one value per tag per timestamp
- `tag_source_mapping` has `is_active` flag for live migration
- Soft delete on `namespace_nodes` (use `deleted_at`)

## Reference

- Schema files: `schemas/*.sql`
- System Spec: `docs/platform_system_spec.md` §5, §6
