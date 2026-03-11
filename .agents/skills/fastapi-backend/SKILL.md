---
name: fastapi-backend
description: >
  FastAPI backend patterns for UNS platform REST and gRPC APIs. Triggers on
  tasks involving API endpoint design, RBAC/JWT authentication, namespace CRUD,
  tag registry, schema type management, data write endpoints, or MCP server.
---

# FastAPI Backend Patterns

## API Structure

```
backend/app/
  ├── main.py              FastAPI app entry
  ├── api/
  │   ├── v1/
  │   │   ├── namespace.py   Namespace CRUD
  │   │   ├── tags.py        Tag registry + query
  │   │   ├── data.py        Data write + query
  │   │   ├── schema_types.py Schema Type CRUD
  │   │   └── acl.py         ACL management
  │   └── deps.py          Shared dependencies
  ├── models/              SQLAlchemy models
  ├── schemas/             Pydantic schemas
  ├── services/            Business logic
  └── core/
      ├── config.py        Settings
      └── security.py      JWT + RBAC
```

## Key Endpoints

### Namespace
- `GET /api/v1/namespace/tree` — Full tree
- `POST /api/v1/namespace/nodes` — Create node
- `PUT /api/v1/namespace/nodes/{id}/move` — Move (triggers Live Migration)
- `DELETE /api/v1/namespace/nodes/{id}` — Soft delete

### Data
- `POST /api/v1/data/{topic_path}` — Write data (→ Data Engine → DB + MQTT)
- `GET /api/v1/tags/{path}/values?from=&to=` — Query history
- `GET /api/v1/tags/{path}/latest` — Latest value

### gRPC (UNSDataService)
- Read: BrowseNamespace, ListTags, QueryTimeSeries, GetLatestValues
- Write: WriteEvent, WriteEventStream
- Context: GetProductionRun, UpdateProductionRun

## Auth

- JWT tokens with RBAC roles: `admin`, `engineer`, `operator`, `readonly`
- API Key support for machine-to-machine

## Data Write Flow

REST/gRPC write → enters same Data Engine pipeline as MQTT
→ Decode → Schema Match → Extract → Persist → also publish to MQTT topic

## Reference

- System Spec: `docs/platform_system_spec.md` §8
- gRPC definitions: `docs/platform_system_spec.md` §8.5
