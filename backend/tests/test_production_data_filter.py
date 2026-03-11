import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ProductionRun, TsEvents, TsAlarms, TsMeasurements, TsStatus, TsMetrics, Tag
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_get_run_data_filter_logic(client: AsyncClient, db_session: AsyncSession):
    """
    Verify that get_run_data correctly filters by (run_id OR lot_id).
    """
    # 1. Create a dummy Tag for events
    tag = Tag(display_name="Test Event Tag", asset_path="Test/Asset", category="events")
    db_session.add(tag)
    await db_session.flush()
    tag_id = tag.tag_id

    # 2. Create a Production Run
    run = ProductionRun(
        lot_id="LOT-FILTER-TEST",
        equipment_path="Test/Asset",
        start_time=datetime.now(timezone.utc),
        step_id="STEP-1",
        status="running"
    )
    db_session.add(run)
    await db_session.flush()
    run_id = run.run_id
    lot_id = "LOT-FILTER-TEST"

    # 3. Create TS data with different ID combinations
    # Event match test
    events = [
        TsEvents(time=datetime.now(timezone.utc), tag_id=tag_id, event_id="E1", event_code="C1", run_id=run_id, lot_id=lot_id),
        TsEvents(time=datetime.now(timezone.utc), tag_id=tag_id, event_id="E2", event_code="C1", run_id=run_id, lot_id=None),
        TsEvents(time=datetime.now(timezone.utc), tag_id=tag_id, event_id="E3", event_code="C1", run_id=None, lot_id=lot_id),
        TsEvents(time=datetime.now(timezone.utc), tag_id=tag_id, event_id="E4", event_code="C1", run_id=run_id+1, lot_id="OTHER-LOT"),
    ]
    
    # Alarm match test
    alarms = [
        TsAlarms(time=datetime.now(timezone.utc), tag_id=tag_id, alarm_id="A1", alarm_code="C1", severity="critical", alarm_status="active", run_id=run_id, lot_id=None),
        TsAlarms(time=datetime.now(timezone.utc), tag_id=tag_id, alarm_id="A2", alarm_code="C1", severity="critical", alarm_status="active", run_id=None, lot_id=lot_id),
    ]

    # Measurements match test
    measurements = [
        TsMeasurements(time=datetime.now(timezone.utc), tag_id=tag_id, value=1.0, run_id=run_id, lot_id=None),
        TsMeasurements(time=datetime.now(timezone.utc), tag_id=tag_id, value=2.0, run_id=None, lot_id=lot_id),
    ]
    
    db_session.add_all(events)
    db_session.add_all(alarms)
    db_session.add_all(measurements)
    await db_session.commit()

    # 4. Call the API
    response = await client.get(f"/api/v1/production-runs/{run_id}/data")
    assert response.status_code == 200
    data = response.json()
    
    # Verify Events
    event_ids = [e["event_id"] for e in data["events"]]
    assert "E1" in event_ids
    assert "E2" in event_ids
    assert "E3" in event_ids
    assert "E4" not in event_ids
    assert len(event_ids) == 3
    
    # Verify Alarms
    alarm_ids = [a["alarm_id"] for a in data["alarms"]]
    assert "A1" in alarm_ids
    assert "A2" in alarm_ids
    assert len(alarm_ids) == 2
    
    # Verify Measurements
    measurement_values = [m["value"] for m in data["measurements"]]
    assert 1.0 in measurement_values
    assert 2.0 in measurement_values
    assert len(measurement_values) == 2
