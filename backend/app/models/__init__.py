"""
SQLAlchemy ORM Models — reflecting DB schema from docker/init-db/
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# ─── Production ────────────────────────────────────────────────

from .production import ProductionRun

# ─── Namespace ────────────────────────────────────────────────


class NamespaceNode(Base):
    __tablename__ = "namespace_nodes"

    node_id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("namespace_nodes.node_id"), nullable=True)
    name = Column(Text, nullable=False)
    node_type = Column(Text, nullable=False)  # structural / topic
    full_path = Column(Text, nullable=False, unique=True)

    # Topic Node 專屬
    schema_id = Column(Integer, ForeignKey("uns_payload_schemas.schema_id"), nullable=True)
    persist_mode = Column(Text, default="db")
    retention_days = Column(Integer, default=90)

    # Metadata
    description = Column(Text, nullable=True)
    icon = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    # NOTE: No ORM relationships — async SQLAlchemy + lazy loading = deadlock.
    #       Use explicit queries in service layer instead.


# ─── UNS Payload Schemas ─────────────────────────────────────────────


class UnsPayloadSchema(Base):
    __tablename__ = "uns_payload_schemas"

    schema_id = Column(Integer, primary_key=True)
    schema_name = Column(Text, nullable=False, unique=True)
    schema_category = Column(Text, default="telemetry")
    decoder = Column(Text, default="json")
    timestamp_field = Column(Text, nullable=True)
    store_raw = Column(Boolean, default=True)
    raw_retention_days = Column(Integer, default=30)
    on_schema_mismatch = Column(Text, default="log_and_store")
    on_new_field = Column(Text, default="suggest")
    fields = Column(JSONB, nullable=False)
    status = Column(Text, default="confirmed")
    is_suggested = Column(Boolean, default=False)
    topic_pattern = Column(Text, nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime(timezone=True), nullable=True)


# ─── Tags ─────────────────────────────────────────────────────


class Tag(Base):
    __tablename__ = "tags"

    tag_id = Column(Integer, primary_key=True)
    display_name = Column(Text, nullable=False)
    asset_path = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    data_point = Column(Text, nullable=True)
    unit = Column(Text, nullable=True)
    data_type = Column(Text, nullable=False, default="float")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_data_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class TagSourceMapping(Base):
    __tablename__ = "tag_source_mapping"

    mapping_id = Column(Integer, primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.tag_id"), nullable=False)
    mqtt_topic = Column(Text, nullable=False, unique=True)
    active = Column(Boolean, nullable=False, default=True)
    mapped_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    mapped_by = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)


class TagChangeLog(Base):
    __tablename__ = "tag_change_log"

    id = Column(Integer, primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.tag_id"), nullable=False)
    change_type = Column(Text, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    changed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    changed_by = Column(Text, nullable=True)


# ─── Time-Series (read-only models for queries) ──────────────


class TsTelemetry(Base):
    __tablename__ = "ts_telemetry"

    # Hypertable — no single PK, use composite
    time = Column(DateTime(timezone=True), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.tag_id"), primary_key=True)
    value = Column(Float, nullable=True)
    value_text = Column(Text, nullable=True)
    value_json = Column(JSONB, nullable=True)
    quality = Column(Text, default="good")
    run_id = Column(Integer, nullable=True)
    lot_id = Column(Text, nullable=True)
    step_id = Column(Text, nullable=True)


class TsStatus(Base):
    __tablename__ = "ts_status"

    time = Column(DateTime(timezone=True), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.tag_id"), primary_key=True)
    state_code = Column(Text, nullable=False)
    sub_state_code = Column(Text, nullable=True)
    code_category = Column(Text, nullable=True)
    mode = Column(Text, nullable=True)
    details = Column(JSONB, nullable=True)
    run_id = Column(Integer, nullable=True)
    lot_id = Column(Text, nullable=True)


class TsAlarms(Base):
    __tablename__ = "ts_alarms"

    time = Column(DateTime(timezone=True), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.tag_id"), primary_key=True)
    alarm_id = Column(Text, nullable=False)
    alarm_code = Column(Text, nullable=False)
    sub_alarm_code = Column(Text, nullable=True)
    code_category = Column(Text, nullable=True)
    severity = Column(Text, nullable=False)
    message = Column(Text, nullable=True)
    alarm_status = Column(Text, nullable=False)
    value = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    details = Column(JSONB, nullable=True)
    run_id = Column(Integer, nullable=True)
    lot_id = Column(Text, nullable=True)


class TsEvents(Base):
    __tablename__ = "ts_events"

    time = Column(DateTime(timezone=True), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.tag_id"), primary_key=True)
    event_id = Column(Text, nullable=False)
    event_code = Column(Text, nullable=False)
    sub_event_code = Column(Text, nullable=True)
    code_category = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    details = Column(JSONB, nullable=True)
    run_id = Column(Integer, nullable=True)
    lot_id = Column(Text, nullable=True)


class TsMetrics(Base):
    __tablename__ = "ts_metrics"

    time = Column(DateTime(timezone=True), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.tag_id"), primary_key=True)
    metric_category = Column(Text, nullable=False)
    metric_code = Column(Text, nullable=False)
    sub_metric_code = Column(Text, nullable=True)
    period = Column(Text, nullable=True)
    values = Column(JSONB, nullable=False)
    context = Column(JSONB, nullable=True)
    details = Column(JSONB, nullable=True)
    run_id = Column(Integer, nullable=True)
    lot_id = Column(Text, nullable=True)


class TsMeasurements(Base):
    __tablename__ = "ts_measurements"

    time = Column(DateTime(timezone=True), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.tag_id"), primary_key=True)
    value = Column(Float, nullable=True)
    spec_upper = Column(Float, nullable=True)
    spec_lower = Column(Float, nullable=True)
    target_value = Column(Float, nullable=True)
    result = Column(Text, nullable=True)
    sample_id = Column(Text, nullable=True)
    sample_position = Column(Text, nullable=True)
    inspector = Column(Text, nullable=True)
    context = Column(JSONB, nullable=True)
    details = Column(JSONB, nullable=True)
    run_id = Column(Integer, nullable=True)
    lot_id = Column(Text, nullable=True)
    step_id = Column(Text, nullable=True)
