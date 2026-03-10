# Handover: Namespace Node & Tag Deletion Safety

## Context
During Phase 3 UI Alignment (Frontend focus), we identified critical data integrity risks related to Namespace Node and Tag deletions. This document outlines the requirements for the Backend Agent to address these risks.

## Backend Requirements

### 1. Cascading Deletion for Namespace Nodes
*   **Location**: `backend/app/services/namespace_service.py`
*   **Soft Delete (`soft_delete_node`)**:
    *   Currently: Only marks the node and its sub-nodes as deleted.
    *   **Requirement**: Must also soft-delete all `Tags` associated with the node's `full_path` prefix (`asset_path` starts with `node.full_path`).
*   **Hard Delete (`hard_delete_node`)**:
    *   Currently: Only deletes the node and its sub-nodes.
    *   **Requirement**: Must also hard-delete all associated `Tags`, which triggers cascading deletes for `tag_source_mapping`, `tag_change_log`, and all historical data in TimescaleDB (`ts_telemetry`, `ts_alarms`, etc.).

### 2. Schema Mapping Validation
*   **Location**: `backend/app/api/v1/schema_types.py` & Pydantic models.
*   **Requirement**: Validate that the `target_column` provided in the schema fields matches the allowed columns for the specified `category` (as defined in ADR-003).

### 3. Data Engine Logic Verification
*   **Location**: `data-engine/src/pipeline.py`
*   **Requirement**: Verify that once a Tag is soft-deleted, the Data Engine stops routing new data to it after the cache is refreshed.

## ADR Reference
- [ADR-003: Target Column Mapping](file:///Users/kaihsiang/Documents/Git_Repository/uns-platform/docs/adr/ADR-003-target-column-mapping.md)
