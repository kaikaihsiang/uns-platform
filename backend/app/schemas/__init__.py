"""
Pydantic Schemas — Request / Response models
"""
from datetime import datetime

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# Namespace
# ═══════════════════════════════════════════════════════════════


class NodeCreate(BaseModel):
    parent_id: int | None = None
    name: str
    node_type: str = Field(pattern=r"^(structural|topic)$")
    description: str | None = None
    schema_type_id: int | None = None


class NodeRename(BaseModel):
    name: str


class NodeMove(BaseModel):
    new_parent_id: int


class NodePersistence(BaseModel):
    persist_mode: str = Field(pattern=r"^(db|retain|passthrough)$")
    retention_days: int = 90


class NodeOut(BaseModel):
    node_id: int
    parent_id: int | None
    name: str
    node_type: str
    full_path: str
    schema_type_id: int | None = None
    persist_mode: str | None = None
    retention_days: int | None = None
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class NodeTreeOut(NodeOut):
    """Node with nested children for tree representation."""
    children: list["NodeTreeOut"] = []

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# Schema Types
# ═══════════════════════════════════════════════════════════════


class SchemaTypeCreate(BaseModel):
    type_name: str
    decoder: str = "json"
    timestamp_field: str | None = None
    store_raw: bool = True
    raw_retention_days: int = 30
    on_schema_mismatch: str = "log_and_store"
    on_new_field: str = "suggest"
    fields: list[dict]


class SchemaTypeUpdate(BaseModel):
    type_name: str | None = None
    decoder: str | None = None
    timestamp_field: str | None = None
    store_raw: bool | None = None
    raw_retention_days: int | None = None
    on_schema_mismatch: str | None = None
    on_new_field: str | None = None
    fields: list[dict] | None = None


class SchemaTypeOut(BaseModel):
    type_id: int
    type_name: str
    decoder: str
    timestamp_field: str | None = None
    store_raw: bool
    raw_retention_days: int
    on_schema_mismatch: str
    on_new_field: str
    fields: list[dict]
    status: str | None = None
    version: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════
# Tags
# ═══════════════════════════════════════════════════════════════


class TagCreate(BaseModel):
    display_name: str
    asset_path: str
    category: str
    data_point: str | None = None
    unit: str | None = None
    data_type: str = "float"
    description: str | None = None


class TagOut(BaseModel):
    tag_id: int
    display_name: str
    asset_path: str
    category: str
    data_point: str | None = None
    unit: str | None = None
    data_type: str
    description: str | None = None
    created_at: datetime | None = None
    last_data_at: datetime | None = None

    model_config = {"from_attributes": True}


class TagMappingOut(BaseModel):
    mapping_id: int
    tag_id: int
    mqtt_topic: str
    active: bool
    mapped_at: datetime | None = None
    mapped_by: str | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}


class TagChangeLogOut(BaseModel):
    id: int
    tag_id: int
    change_type: str
    old_value: str | None = None
    new_value: str | None = None
    reason: str | None = None
    changed_at: datetime | None = None
    changed_by: str | None = None

    model_config = {"from_attributes": True}


class TagDetailOut(BaseModel):
    """Tag with its mappings and change history."""
    tag: TagOut
    mappings: list[TagMappingOut] = []
    history: list[TagChangeLogOut] = []


class TagValueOut(BaseModel):
    time: datetime
    value: float | None = None
    value_text: str | None = None
    quality: str | None = None


class TagValuesResponse(BaseModel):
    tag_id: int
    tag: TagOut | None = None
    data: list[TagValueOut] = []


class TagLatestResponse(BaseModel):
    tag_id: int
    tag: TagOut | None = None
    latest: TagValueOut | None = None


# ═══════════════════════════════════════════════════════════════
# Data Write
# ═══════════════════════════════════════════════════════════════


class DataWriteRequest(BaseModel):
    timestamp: datetime | None = None
    payload: dict
