from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.models import Base


class ProductionRun(Base):
    __tablename__ = "production_run"

    run_id = Column(Integer, primary_key=True)
    lot_id = Column(Text, nullable=False)
    parent_lot_id = Column(Text, nullable=True)
    equipment_path = Column(Text, nullable=False)
    chamber_id = Column(Text, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    step_id = Column(Text, nullable=False)
    pass_number = Column(Integer, default=1)
    recipe_id = Column(Text, nullable=True)
    recipe_version = Column(Text, nullable=True)
    product_id = Column(Text, nullable=True)
    status = Column(Text, default="running")
    result = Column(Text, nullable=True)
    qty_in = Column(Integer, nullable=True)
    qty_out = Column(Integer, nullable=True)
    context = Column(JSONB, nullable=True)
    source = Column(Text, default="cdc")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
