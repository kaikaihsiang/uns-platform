"""
Data Write API
"""
import json
import traceback
from datetime import datetime, timezone

import asyncio
import os
import paho.mqtt.publish as publish
from fastapi import APIRouter, Depends, HTTPException

from app.schemas import DataWriteRequest

router = APIRouter(prefix="/data", tags=["Data"])


@router.post("/{topic_path:path}")
async def write_data(
    topic_path: str,
    body: DataWriteRequest,
):
    """
    寫入資料到指定 topic。
    修正版：不再 Bypass 直接寫 DB，而是將收到的 payload Publish 到 EMQX Broker，
    交由背景的 Data Engine 訂閱處理。
    """
    try:
        ts = body.timestamp or datetime.now(timezone.utc)
        payload_json = json.dumps(body.payload, ensure_ascii=False)
        mqtt_host = os.getenv("MQTT_BROKER_HOST", "localhost")
        mqtt_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))

        # 在 background thread 執行 blocking MQTT 發送
        await asyncio.to_thread(
            publish.single,
            topic=topic_path,
            payload=payload_json,
            hostname=mqtt_host,
            port=mqtt_port,
            qos=1
        )

        return {
            "status": "accepted",
            "topic": topic_path,
            "timestamp": ts.isoformat(),
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
