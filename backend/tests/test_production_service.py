from datetime import datetime, timedelta, timezone

import pytest
from app.models import TsAlarms, TsTelemetry
from app.schemas.production import ProductionRunCreate
from app.services.production_service import ProductionService


@pytest.mark.asyncio
async def test_create_run_auto_complete_previous(db_session):
    """驗證建立新 Run 時，舊的 Active Run 會被自動關閉。"""
    svc = ProductionService()
    
    # 1. 建立第一個 Run
    run1_in = ProductionRunCreate(
        equipment_path="Line1/Mixer",
        lot_id="LOT-001",
        recipe_id="REC-A",
        step_id="STEP-1",
        status="running",
        start_time=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    run1 = await svc.create_run(db_session, run1_in)
    assert run1.status == "running"
    
    # 2. 在同一個設備路徑建立第二個 Run
    run2_in = ProductionRunCreate(
        equipment_path="Line1/Mixer",
        lot_id="LOT-002",
        recipe_id="REC-B",
        step_id="STEP-1",
        status="running"
    )
    run2 = await svc.create_run(db_session, run2_in)
    
    # 3. 驗證第一個 Run 被自動關閉
    await db_session.refresh(run1)
    assert run1.status == "completed"
    assert run1.end_time is not None
    assert "Auto-closed" in run1.result
    
    # 4. 驗證第二個 Run 是 running
    assert run2.status == "running"
    assert run2.lot_id == "LOT-002"

@pytest.mark.asyncio
async def test_get_run_data_aggregation(db_session):
    """驗證 get_run_data 是否能跨表聚合資料。"""
    svc = ProductionService()
    
    # 1. 建立一個 Run
    run_in = ProductionRunCreate(
        equipment_path="Line1/Mixer",
        lot_id="LOT-DATA-TEST",
        step_id="STEP-1",
        status="running"
    )
    run = await svc.create_run(db_session, run_in)
    
    # 2. 建立一個 Tag
    from app.services import tag_service
    tag = await tag_service.create_tag(db_session, asset_path="Line1/Mixer/Telemetry", display_name="Temp", category="telemetry")
    
    # 3. 模擬寫入時序資料 (Telemetry & Alarm)
    t1 = TsTelemetry(time=datetime.now(timezone.utc), tag_id=tag.tag_id, value=100.5, run_id=run.run_id)
    a1 = TsAlarms(time=datetime.now(timezone.utc), tag_id=tag.tag_id, alarm_id="ALM-1", alarm_code="E01", severity="critical", alarm_status="active", run_id=run.run_id)
    db_session.add_all([t1, a1])
    await db_session.commit()
    
    # 4. 呼叫 get_run_data
    data = await svc.get_run_data(db_session, run.run_id)
    
    # 5. 驗證資料存在
    assert len(data["telemetry"]) == 1
    assert data["telemetry"][0]["value"] == 100.5
    assert len(data["alarms"]) == 1
    assert data["alarms"][0]["alarm_code"] == "E01"
    
    # 6. 驗證 Metadata Enrichment (display_name 應該被帶出來)
    assert data["telemetry"][0]["display_name"] == "Temp"

@pytest.mark.asyncio
async def test_search_history_runs(db_session):
    """驗證歷史查詢過濾邏輯。"""
    svc = ProductionService()
    
    # 建立多個不同 Lot 的 Run
    await svc.create_run(db_session, ProductionRunCreate(equipment_path="L1", lot_id="LOT-AAA", step_id="S1", status="completed"))
    await svc.create_run(db_session, ProductionRunCreate(equipment_path="L1", lot_id="LOT-BBB", step_id="S1", status="completed"))
    
    # 關鍵字搜尋
    results = await svc.search_history_runs(db_session, lot_id="AAA")
    assert len(results) == 1
    assert results[0].lot_id == "LOT-AAA"
