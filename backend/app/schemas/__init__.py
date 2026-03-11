"""
Pydantic Schemas — Request / Response models
"""
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

# ═══════════════════════════════════════════════════════════════
# Namespace
# ═══════════════════════════════════════════════════════════════


class NodeCreate(BaseModel):
    parent_id: int | None = None
    name: str
    node_type: str = Field(pattern=r"^(structural|topic)$")
    description: str | None = None
    schema_id: int | None = None


class NodeRename(BaseModel):
    name: str


class NodeSchemaUpdate(BaseModel):
    schema_id: int | None = None


class NodeMove(BaseModel):
    new_parent_id: int | None = None


class NodePersistence(BaseModel):
    persist_mode: str = Field(pattern=r"^(db|retain|passthrough)$")
    retention_days: int = 90


class NodeOut(BaseModel):
    node_id: int
    parent_id: int | None
    name: str
    node_type: str
    full_path: str
    schema_id: int | None = None
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


class SchemaField(BaseModel):
    name: str
    path: str
    type: str = "float"
    unit: str | None = None
    extract: bool = True
    persist: bool = True
    deadband: str | float | None = None
    array_mode: str = "single"
    target_column: str | None = None


class PayloadSchemaCreate(BaseModel):
    schema_name: str
    decoder: str = "json"
    timestamp_field: str | None = None
    store_raw: bool = True
    raw_retention_days: int = 30
    on_schema_mismatch: str = "log_and_store"
    on_new_field: str = "suggest"
    fields: list[SchemaField]
    schema_category: str = Field(default="telemetry", pattern=r"^(telemetry|status|alarm|event|measurement|metrics)$")

    @model_validator(mode="after")
    def validate_target_columns(self) -> "PayloadSchemaCreate":
        allowed_targets = {
            "telemetry": set(),
            "status": {"state_code", "sub_state_code", "code_category", "mode", "details"},
            "alarm": {"alarm_id", "alarm_code", "sub_alarm_code", "code_category", "severity", "message", "alarm_status", "value", "threshold", "details"},
            "event": {"event_id", "event_code", "sub_event_code", "code_category", "result", "lot_id", "sample_id", "details"},
            "measurement": {"value", "spec_upper", "spec_lower", "target_value", "result", "lot_id", "sample_id", "sample_position", "inspector", "details"},
            "metrics": {"metric_category", "metric_code", "sub_metric_code", "period", "values", "details"},
        }
        category = self.schema_category
        valid_set = allowed_targets.get(category, set())

        for field in self.fields:
            target = field.target_column
            if target is not None:
                if not valid_set:
                    raise ValueError(f"Category '{category}' does not support target_column mapping (field: {field.name}).")
                if str(target) not in valid_set:
                    raise ValueError(f"Invalid target_column '{target}' for category '{category}'. Allowed: {valid_set}")
        return self


class PayloadSchemaUpdate(BaseModel):
    schema_name: str | None = None
    decoder: str | None = None
    timestamp_field: str | None = None
    store_raw: bool | None = None
    raw_retention_days: int | None = None
    on_schema_mismatch: str | None = None
    on_new_field: str | None = None
    fields: list[SchemaField] | None = None
    schema_category: str | None = Field(default=None, pattern=r"^(telemetry|status|alarm|event|measurement|metrics)$")

    @model_validator(mode="after")
    def validate_target_columns(self) -> "PayloadSchemaUpdate":
        if not self.fields or not self.schema_category:
            return self

        allowed_targets = {
            "telemetry": set(),
            "status": {"state_code", "sub_state_code", "code_category", "mode", "details"},
            "alarm": {"alarm_id", "alarm_code", "sub_alarm_code", "code_category", "severity", "message", "alarm_status", "value", "threshold", "details"},
            "event": {"event_id", "event_code", "sub_event_code", "code_category", "result", "lot_id", "sample_id", "details"},
            "measurement": {"value", "spec_upper", "spec_lower", "target_value", "result", "lot_id", "sample_id", "sample_position", "inspector", "details"},
            "metrics": {"metric_category", "metric_code", "sub_metric_code", "period", "values", "details"},
        }
        category_str = str(self.schema_category)
        valid_set = allowed_targets.get(category_str, set())

        for field in self.fields:
             target = field.target_column
             if target is not None:
                 if not valid_set:
                     raise ValueError(f"Category '{self.schema_category}' does not support target_column mapping (field: {field.name}).")
                 if str(target) not in valid_set:
                     raise ValueError(f"Invalid target_column '{target}' for category '{self.schema_category}'. Allowed: {valid_set}")
        return self


class PayloadSchemaOut(BaseModel):
    schema_id: int
    schema_name: str
    decoder: str
    timestamp_field: str | None = None
    store_raw: bool
    raw_retention_days: int
    on_schema_mismatch: str
    on_new_field: str
    schema_category: str
    fields: list[SchemaField]
    status: str | None = None
    is_suggested: bool = False
    topic_pattern: str | None = None
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


class TagUpdate(BaseModel):
    display_name: str | None = None
    category: str | None = None
    data_point: str | None = None
    unit: str | None = None
    data_type: str | None = None
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
