from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct
from pydantic import BaseModel

from app.proto import uns_data_service_pb2
from app.services.semantic_service import SemanticDataService

router = APIRouter(prefix="/semantic", tags=["Semantic"])
semantic_service = SemanticDataService()

class SemanticPoint(BaseModel):
    path: str
    tag_id: str
    ts: str
    category: str
    display_value: str
    data: dict
    context_data: dict
    run_id: Optional[str]

class PublishRequest(BaseModel):
    path: str
    data: dict
    timestamp: Optional[datetime] = None

@router.get("/snapshot", response_model=List[SemanticPoint])
async def get_snapshot(
    paths: List[str] = Query(..., description="支援 Wildcard 的路徑清單"),
):
    """
    取得多路徑最新狀態快照 (REST 映射)。
    """
    request = uns_data_service_pb2.GetSnapshotRequest(paths=paths)
    response = await semantic_service.GetSnapshot(request, None)
    
    result = []
    for p in response.points:
        result.append(SemanticPoint(
            path=p.path,
            tag_id=p.tag_id,
            ts=datetime.fromtimestamp(p.ts.seconds, tz=timezone.utc).isoformat() if p.ts.seconds else "",
            category=p.category,
            display_value=p.display_value,
            data=MessageToDict(p.data),
            context_data=dict(p.context_data),
            run_id=p.current_run_id
        ))
    return result

@router.post("/publish")
async def publish_data(body: PublishRequest):
    """
    語義寫回：透過路徑發布資料。
    """
    data_struct = Struct()
    ParseDict(body.data, data_struct)

    request = uns_data_service_pb2.PublishDataRequest(
        path=body.path,
        data=data_struct
    )
    if body.timestamp:
        from google.protobuf.timestamp_pb2 import Timestamp
        ts = Timestamp()
        ts.FromDatetime(body.timestamp)
        request.ts.CopyFrom(ts)
        
    response = await semantic_service.PublishData(request, None)
    if not response.success:
        raise HTTPException(status_code=500, detail=response.message)
    return {"status": "accepted", "message": response.message}

@router.get("/search")
async def search_namespace(
    base_path: Optional[str] = Query(None),
    attributes: dict = Depends(lambda: {}) 
):
    """
    語義搜尋：屬性反查路徑。
    """
    request = uns_data_service_pb2.SearchNamespaceRequest(
        base_path=base_path,
        attributes=attributes
    )
    response = await semantic_service.SearchNamespace(request, None)
    return response.matches
