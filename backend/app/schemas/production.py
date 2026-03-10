from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ProductionRunBase(BaseModel):
    lot_id: str = Field(..., description="The unique Lot ID")
    parent_lot_id: Optional[str] = None
    equipment_path: str = Field(..., description="The full namespace path to the equipment")
    chamber_id: Optional[str] = None
    step_id: str = Field(..., description="The manufacturing step ID")
    pass_number: int = 1
    recipe_id: Optional[str] = None
    recipe_version: Optional[str] = None
    product_id: Optional[str] = None
    status: str = Field("running", description="Current status of the run, e.g. running, completed, aborted")
    result: Optional[str] = None
    qty_in: Optional[int] = None
    qty_out: Optional[int] = None
    context: Optional[Dict[str, Any]] = None
    source: str = "api"


class ProductionRunCreate(ProductionRunBase):
    start_time: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductionRunUpdate(BaseModel):
    status: Optional[str] = None
    end_time: Optional[datetime] = None
    result: Optional[str] = None
    qty_out: Optional[int] = None
    context: Optional[Dict[str, Any]] = None


class ProductionRunOut(ProductionRunBase):
    run_id: int
    start_time: datetime
    end_time: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True
