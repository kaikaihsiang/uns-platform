---
name: uns-namespace-design
description: >
  UNS namespace hierarchy design following ISA-95 standards. Triggers on tasks
  involving namespace tree structure, node types (structural/topic), topic naming
  conventions, tag identity management (tag_id separation), live migration,
  event topic design (category-based), or full_path ↔ MQTT topic mapping.
---

# UNS Namespace Design

## Core Principles

1. **Namespace Tree = ISA-95 Hierarchy**
   - Enterprise / Site / Area / Line / Equipment
   - Node types: `structural` (hierarchy only) or `topic` (MQTT-enabled)

2. **full_path = MQTT Topic**
   - `namespace_nodes.full_path` is always identical to the MQTT topic path
   - Namespace Manager is the authoritative source for all topics

3. **Tag Identity Separation**
   - `tag_id` is permanent and never changes
   - `tag_source_mapping` links MQTT topics → tag_ids (can be updated)
   - Historical data is always queried by `tag_id`, not by topic path

4. **Live Migration**
   - Moving a node updates `full_path` and `tag_source_mapping`
   - `tag_id` stays the same → historical data continuity
   - Must also update: EMQX ACL, audit log, downstream consumers

## Event Topic Design

- Use **category-based** topics, NOT per-event topics
- Topic = location (which equipment, which category): `.../Event/Process`
- Payload field = content (which event type): `event_code: "ProcessStarted"`
- 5 standard categories: Process, Recipe, Lot, Quality, Maintenance
- Adding a new event_code within a category requires NO namespace/topic changes

## Reference

- System Spec: `docs/platform_system_spec.md` §3, §7, §12, §13
- Namespace template: `docs/namespace_template.yaml`
- Topic naming guide: `docs/topic_naming_guide.md`
