---
name: mqtt-emqx-integration
description: >
  EMQX MQTT broker integration for UNS platform. Triggers on tasks involving
  MQTT client implementation, ACL synchronization, topic subscription patterns,
  EMQX REST API usage, broker configuration, or consumer design.
---

# MQTT EMQX Integration

## EMQX Version

- **EMQX Open Source 5.x** (not Enterprise)
- Deployed via Docker
- REST API on port 18083 (default)

## ACL Synchronization

```
Namespace Manager ACL change
  → Platform Backend calls EMQX REST API
  → PUT /api/v5/authorization/sources/built_in_database/rules/users/{username}
  → Updates topic-level publish/subscribe permissions
```

ACL inherits from parent nodes — child nodes get parent's ACL unless overridden.

## Consumer Patterns

- Subscribe to `#` (all topics) for the main Data Engine consumer
- Use shared subscription `$share/data-engine/#` for load balancing
- Wildcard subscriptions for specific use cases:
  - `+/+/+/+/+/Event/#` — all events across factory
  - `+/+/+/+/+/Telemetry` — all telemetry
  - `Enterprise/Site/Area/Line1/#` — everything on Line1

## Data Flow

All data entering UNS (REST, gRPC, CDC) is ultimately published to the
corresponding MQTT topic, ensuring all real-time consumers receive it.

## Reference

- System Spec: `docs/platform_system_spec.md` §4, §8, §9
- Config example: `docs/uns_config_example.yaml`
