"""
SQLAlchemy ORM Models — reflecting DB schema from docker/init-db/
"""
from datetime import datetime

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


# ─── Namespace ────────────────────────────────────────────────


class NamespaceNode(Base):
    __tablename__ = "namespace_nodes"

    node_id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("namespace_nodes.node_id"), nullable=True)
    name = Column(Text, nullable=False)
    node_type = Column(Text, nullable=False)  # structural / topic
    full_path = Column(Text, nullable=False, unique=True)

    # Topic Node 專屬
    schema_type_id = Column(Integer, ForeignKey("schema_types.type_id"), nullable=True)
    persist_mode = Column(Text, default="db")
    retention_days = Column(Integer, default=90)

    # Metadata
    description = Column(Text, nullable=True)
    icon = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    # NOTE: No ORM relationships — async SQLAlchemy + lazy loading = deadlock.
    #       Use explicit queries in service layer instead.


# ─── Schema Types ─────────────────────────────────────────────


class SchemaType(Base):
    __tablename__ = "schema_types"

    type_id = Column(Integer, primary_key=True)
    type_name = Column(Text, nullable=False, unique=True)
    decoder = Column(Text, default="json")
    timestamp_field = Column(Text, nullable=True)
    store_raw = Column(Boolean, default=True)
    raw_retention_days = Column(Integer, default=30)
    on_schema_mismatch = Column(Text, default="log_and_store")
    on_new_field = Column(Text, default="suggest")
    fields = Column(JSONB, nullable=False)
    status = Column(Text, default="confirmed")
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)


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
    created_at = Column(DateTime(timezone=True), default=datetime.now)
    last_data_at = Column(DateTime(timezone=True), nullable=True)


class TagSourceMapping(Base):
    __tablename__ = "tag_source_mapping"

    mapping_id = Column(Integer, primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.tag_id"), nullable=False)
    mqtt_topic = Column(Text, nullable=False, unique=True)
    active = Column(Boolean, nullable=False, default=True)
    mapped_at = Column(DateTime(timezone=True), default=datetime.now)
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
    changed_at = Column(DateTime(timezone=True), default=datetime.now)
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
