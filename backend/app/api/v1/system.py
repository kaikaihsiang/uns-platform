"""
System Settings API — Platform info, MQTT stats, retention policies
"""
import asyncio
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import engine, get_db

router = APIRouter(prefix="/system", tags=["System Settings"])


# ─── Helpers ──────────────────────────────────────────────────


async def _get_emqx_token() -> str | None:
    """Login to EMQX Dashboard and get Bearer token."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{settings.emqx_api_url}/api/v5/login",
                json={"username": settings.emqx_api_user, "password": settings.emqx_api_password},
            )
            resp.raise_for_status()
            return resp.json().get("token")
    except Exception:
        return None


async def _fetch_emqx_stats() -> dict:
    """Fetch stats from EMQX REST API using Bearer token auth."""
    try:
        token = await _get_emqx_token()
        if not token:
            raise ValueError("Failed to obtain EMQX token")

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.emqx_api_url}/api/v5/stats",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            raw = resp.json()

            # EMQX v5 returns a list with one element or a dict
            data = raw[0] if isinstance(raw, list) else raw

            return {
                "connected_clients": data.get("connections.count", 0),
                "topics_count": data.get("topics.count", 0),
                "subscriptions_count": data.get("subscriptions.count", 0),
                "messages_received_total": data.get("messages.received", 0),
                "messages_sent_total": data.get("messages.sent", 0),
                "messages_per_second": round(
                    data.get("messages.received", 0) / max(1, data.get("stats.uptime", 1)) * 1000, 2
                ) if data.get("stats.uptime") else 0,
                "retained_messages_count": data.get("retained_msg.count", 0),
            }
    except Exception as e:
        return {
            "error": str(e),
            "connected_clients": 0,
            "topics_count": 0,
            "subscriptions_count": 0,
            "messages_received_total": 0,
            "messages_sent_total": 0,
            "messages_per_second": 0,
            "retained_messages_count": 0,
        }


async def _fetch_emqx_version() -> dict:
    """Fetch version/status from EMQX."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.emqx_api_url}/api/v5/status",
            )
            if resp.status_code == 200:
                # EMQX v5 /status returns plain text like "emqx is running"
                return {"status": "connected", "version": resp.text.strip()}
            return {"status": "connected", "version": "EMQX 5.x"}
    except Exception:
        return {"status": "disconnected", "version": "unknown"}


# ═══════════════════════════════════════════════════════════════
# Task 1: GET /system/info (P0)
# ═══════════════════════════════════════════════════════════════


@router.get("/info")
async def get_system_info(db: AsyncSession = Depends(get_db)):
    """
    平台資訊 — 各服務連線狀態、版本、uptime。
    """

    # DB status
    db_info = {"status": "disconnected", "version": "unknown", "connection_pool": {}}
    try:
        result = await db.execute(text("SELECT version()"))
        version_str = result.scalar()
        pool = engine.pool
        db_info = {
            "status": "connected",
            "version": version_str,
            "connection_pool": {
                "size": pool.size(),
                "checked_out": pool.checkedout(),
            },
        }
    except Exception as e:
        db_info["error"] = str(e)

    # EMQX status
    emqx_info = await _fetch_emqx_version()
    emqx_info["host"] = f"{settings.mqtt_broker_host}:{settings.mqtt_broker_port}"

    # Uptime
    import app.main as main_module
    start_time = getattr(main_module.app.state, "start_time", None)
    uptime = int(time.time() - start_time) if start_time else 0

    return {
        "platform_version": settings.platform_version,
        "backend_status": "ok",
        "database": db_info,
        "mqtt_broker": emqx_info,
        "uptime_seconds": uptime,
    }


# ═══════════════════════════════════════════════════════════════
# Task 2: GET /system/mqtt-stats (P1)
# ═══════════════════════════════════════════════════════════════


@router.get("/mqtt-stats")
async def get_mqtt_stats():
    """MQTT Broker 統計快照。"""
    return await _fetch_emqx_stats()


# ═══════════════════════════════════════════════════════════════
# Task 3: WebSocket /system/mqtt-stats/ws (P1)
# ═══════════════════════════════════════════════════════════════


@router.websocket("/mqtt-stats/ws")
async def mqtt_stats_ws(websocket: WebSocket):
    """每 5 秒推送 MQTT Broker 統計更新。"""
    await websocket.accept()
    try:
        while True:
            stats = await _fetch_emqx_stats()
            await websocket.send_json(stats)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# Task 4: GET /system/retention (P2)
# ═══════════════════════════════════════════════════════════════


@router.get("/retention")
async def get_retention_policies(db: AsyncSession = Depends(get_db)):
    """各 hypertable 的 retention period 與 compression 狀態。"""
    policies = []

    # Query hypertables
    try:
        ht_result = await db.execute(text("""
            SELECT hypertable_name
            FROM timescaledb_information.hypertables
            ORDER BY hypertable_name
        """))
        hypertables = [row[0] for row in ht_result.fetchall()]
    except Exception:
        hypertables = ["ts_telemetry", "ts_status", "ts_alarms", "ts_events", "ts_metrics", "ts_raw_payloads"]

    # Query compression settings
    compression_map = {}
    try:
        comp_result = await db.execute(text("""
            SELECT hypertable_name, compress_after::text
            FROM timescaledb_information.jobs j
            JOIN timescaledb_information.job_stats js ON j.job_id = js.job_id
            WHERE j.proc_name = 'policy_compression'
        """))
        for row in comp_result.fetchall():
            compression_map[row[0]] = row[1]
    except Exception:
        pass

    # Query retention policies
    retention_map = {}
    try:
        ret_result = await db.execute(text("""
            SELECT hypertable_name, drop_after::text
            FROM timescaledb_information.jobs j
            JOIN timescaledb_information.job_stats js ON j.job_id = js.job_id
            WHERE j.proc_name = 'policy_retention'
        """))
        for row in ret_result.fetchall():
            retention_map[row[0]] = row[1]
    except Exception:
        pass

    for ht in hypertables:
        compress_after = compression_map.get(ht)
        retention = retention_map.get(ht)

        policies.append({
            "table_name": ht,
            "retention_days": _parse_interval_days(retention) if retention else None,
            "compression_enabled": ht in compression_map,
            "compress_after_days": _parse_interval_days(compress_after) if compress_after else None,
        })

    return {"policies": policies}


def _parse_interval_days(interval_str: str | None) -> int | None:
    """Parse PostgreSQL interval string to approximate days."""
    if not interval_str:
        return None
    try:
        # Handle "X days" format
        if "day" in interval_str:
            return int(interval_str.split()[0])
        # Handle "X mons" format (approx 30 days/month)
        if "mon" in interval_str:
            return int(interval_str.split()[0]) * 30
        return int(interval_str)
    except (ValueError, IndexError):
        return None


# ═══════════════════════════════════════════════════════════════
# Task 5: PUT /system/retention (P2 — stub)
# ═══════════════════════════════════════════════════════════════


@router.put("/retention")
async def update_retention():
    """修改資料保留策略（Phase 2 實作）。"""
    raise HTTPException(501, "Retention policy modification is planned for Phase 2")
