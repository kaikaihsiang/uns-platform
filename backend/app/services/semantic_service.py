"""
UNS Semantic Data Service — gRPC & REST Implementation
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import grpc
import paho.mqtt.publish as publish
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy import select

from app.core.database import async_session
from app.models import (
    LatestValue,
    Tag,
    TagSourceMapping,
)
from app.proto import uns_data_service_pb2, uns_data_service_pb2_grpc

logger = logging.getLogger("uns.semantic_service")

def datetime_to_timestamp(dt: datetime) -> Timestamp:
    """Convert python datetime to protobuf Timestamp."""
    if not dt:
        return None
    ts = Timestamp()
    ts.FromDatetime(dt)
    return ts

class SemanticDataService(uns_data_service_pb2_grpc.UNSDataServiceServicer):
    """
    gRPC Servicer for UNS Semantic Data Layer.
    Uses tag_source_mapping and the new latest_values schema.
    """

    async def GetSnapshot(self, request, context):  # noqa: N802
        """取得多路徑最新狀態快照。"""
        async with async_session() as db:
            points = []
            for path_pattern in request.paths:
                sql_pattern = path_pattern.replace("**", "%").replace("*", "%")
                
                stmt = (
                    select(TagSourceMapping, Tag, LatestValue)
                    .join(Tag, TagSourceMapping.tag_id == Tag.tag_id)
                    .outerjoin(LatestValue, Tag.tag_id == LatestValue.tag_id)
                    .where(TagSourceMapping.mqtt_topic.like(sql_pattern))
                    .where(TagSourceMapping.active.is_(True))
                    .where(Tag.deleted_at.is_(None))
                )
                
                result = await db.execute(stmt)
                for mapping, tag, lv in result:
                    semantic_path = mapping.mqtt_topic
                    data_struct = Struct()

                    if lv:
                        # Use data from latest_values if available
                        ts_val = datetime_to_timestamp(lv.time)
                        display_value = lv.display_value or ""
                        category = lv.category
                        if isinstance(lv.data, dict):
                            ParseDict(lv.data, data_struct)
                        context_data = {k: str(v) for k, v in (lv.context_data or {}).items()}
                        run_id = str(lv.run_id) if lv.run_id else ""
                    else:
                        # Fallback to tag defaults if no snapshot exists
                        ts_val = datetime_to_timestamp(tag.created_at)
                        display_value = "No data"
                        category = tag.category
                        context_data = {k: str(v) for k, v in (tag.extra_metadata or {}).items()}
                        run_id = ""

                    points.append(uns_data_service_pb2.SemanticDataPoint(
                        path=semantic_path,
                        tag_id=str(tag.tag_id),
                        ts=ts_val,
                        category=category,
                        display_value=display_value,
                        data=data_struct,
                        context_data=context_data,
                        current_run_id=run_id
                    ))

            
            return uns_data_service_pb2.GetSnapshotResponse(points=points)

    async def QueryHistory(self, request, context):  # noqa: N802
        """拉取歷史數據串流。"""
        logger.warning("QueryHistory requested but not fully implemented")
        yield uns_data_service_pb2.SemanticDataPoint(path="system/status", display_value="NOT_IMPLEMENTED")

    async def SearchNamespace(self, request, context):  # noqa: N802
        """語義探索：基於屬性反查路徑。"""
        async with async_session() as db:
            stmt = (
                select(TagSourceMapping, Tag)
                .join(Tag, TagSourceMapping.tag_id == Tag.tag_id)
                .where(Tag.deleted_at.is_(None))
                .where(TagSourceMapping.active.is_(True))
            )
            
            if request.base_path:
                stmt = stmt.where(TagSourceMapping.mqtt_topic.like(f"{request.base_path}%"))
            
            for k, v in request.attributes.items():
                stmt = stmt.where(Tag.extra_metadata[k].astext == v)
            
            result = await db.execute(stmt)
            matches = []
            for mapping, tag in result:
                matches.append(uns_data_service_pb2.SearchNamespaceResponse.NodeMatch(
                    path=mapping.mqtt_topic,
                    tag_id=str(tag.tag_id),
                    attributes={k: str(v) for k, v in (tag.extra_metadata or {}).items()}
                ))
            
            return uns_data_service_pb2.SearchNamespaceResponse(matches=matches)

    async def PublishData(self, request, context):  # noqa: N802
        """語義寫回：將資料發布至 MQTT。"""
        # This logic remains largely the same, as it deals with incoming data
        # before it hits the Data Engine, not retrieving it from latest_values.
        # But we need to handle the new `data` field in the request.
        try:
            mqtt_topic = request.path
            mqtt_host = os.getenv("MQTT_BROKER_HOST", "localhost")
            mqtt_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
            
            # The request `data` is already a protobuf Struct, we convert it to a dict
            payload_to_send = MessageToDict(request.data)
            
            if request.ts and "timestamp" not in payload_to_send:
                payload_to_send["timestamp"] = datetime.fromtimestamp(request.ts.seconds, tz=timezone.utc).isoformat()
            
            await asyncio.to_thread(
                publish.single,
                topic=mqtt_topic,
                payload=json.dumps(payload_to_send),
                hostname=mqtt_host,
                port=mqtt_port,
                qos=1
            )
            
            return uns_data_service_pb2.PublishDataResponse(success=True, message=f"Published to {mqtt_topic}")
        except Exception as e:
            logger.error("PublishData error: %s", e)
            return uns_data_service_pb2.PublishDataResponse(success=False, message=str(e))

async def serve_grpc():
    """啟動 gRPC 伺服器。"""
    server = grpc.aio.server()
    uns_data_service_pb2_grpc.add_UNSDataServiceServicer_to_server(
        SemanticDataService(), server
    )
    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)
    logger.info("Starting gRPC server on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()
