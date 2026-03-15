import argparse
import json
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

# Configuration
BROKER = "localhost"
PORT = 1883
BASE_MOUNTER = "TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01"
BASE_AOI = "TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-AOI-01"

# Topics
T_MOUNTER_TEL = f"{BASE_MOUNTER}/Telemetry"
T_MOUNTER_STAT = f"{BASE_MOUNTER}/Status"
T_MOUNTER_ALM = f"{BASE_MOUNTER}/Alarms"
T_MOUNTER_MET = f"{BASE_MOUNTER}/Metrics"
T_MOUNTER_EVT = f"{BASE_MOUNTER}/Events"
T_AOI_MEASURE = f"{BASE_AOI}/Measurements"

def timestamp_utc():
    return datetime.now(timezone.utc).isoformat()

def get_meta(category, source):
    return {
        "category": category,
        "schema_version": "1.0",
        "source": source,
        "timestamp": timestamp_utc(),
        "quality": "good"
    }

def publish_scenario_telemetry(client):
    source = BASE_MOUNTER
    payload = {
        "_meta": get_meta("Telemetry", source),
        "data": {
            "values": {
                "temp": round(random.uniform(40, 45), 1),
                "press": round(random.uniform(0.5, 0.6), 2),
                "vib": round(random.uniform(0.8, 1.2), 2)
            },
            "units": {
                "temp": "°C",
                "press": "kPa",
                "vib": "mm/s"
            },
            "usl": 50.0,
            "lsl": 30.0,
            "target": 40.0
        }
    }
    client.publish(T_MOUNTER_TEL, json.dumps(payload))
    print(f"📈 [Telemetry] Sent: {payload['data']['values']}")

def publish_scenario_status(client, state="PRD", sub_state="RUN"):
    source = BASE_MOUNTER
    payload = {
        "_meta": get_meta("Status", source),
        "data": {
            "state": state,
            "sub_state": sub_state,
            "mode": "auto",
            "since": timestamp_utc()
        }
    }
    client.publish(T_MOUNTER_STAT, json.dumps(payload), retain=True)
    print(f"🔄 [Status] Sent: {state}/{sub_state}")

def publish_scenario_alarm(client):
    source = BASE_MOUNTER
    payload = {
        "_meta": get_meta("Alarm", source),
        "data": {
            "alarm_id": f"ALM-{int(time.time())}",
            "alarm_code": "E-VAC-001",
            "severity": "critical",
            "message": "Vacuum Pump Failed",
            "state": "active"
        }
    }
    client.publish(T_MOUNTER_ALM, json.dumps(payload), retain=True)
    print(f"🚨 [Alarm] Sent: {payload['data']['alarm_code']} - {payload['data']['severity']}")

def publish_scenario_event(client, event_code="UNIT_IN", lot_id="LOT-2026-0001", unit_id="PCB-001"):
    # Real-world behavior: Events are sent to the Mounter topic
    # The Data Engine will now handle the up-leveling to the Line context
    source = BASE_MOUNTER
    target_topic = T_MOUNTER_EVT
        
    payload = {
        "_meta": get_meta("Event", source),
        "data": {
            "event_code": event_code,
            "event_id": f"EVT-{int(time.time())}",
            "lot_id": lot_id,
            "unit_id": unit_id
        }
    }
    client.publish(target_topic, json.dumps(payload))
    print(f"📦 [Event] Sent: {event_code} to {target_topic} (Lot:{lot_id}, Unit:{unit_id})")

def publish_scenario_measurement(client):
    source = BASE_AOI
    payload = {
        "_meta": get_meta("Measurement", source),
        "data": {
            "panel_id": "PCB-M1-1002",
            "component_ref": "U12",
            "is_pass": True,
            "offset_x": round(random.uniform(0.01, 0.02), 3),
            "instrument_id": "AOI-CAL-99"
        }
    }
    client.publish(T_AOI_MEASURE, json.dumps(payload))
    print(f"📏 [Measurement] Sent: {payload['data']['panel_id']} Result: {payload['data']['is_pass']}")

def publish_scenario_metrics(client):
    source = BASE_MOUNTER
    payload = {
        "_meta": get_meta("Metrics", source),
        "data": {
            "metric_category": "OEE_STATS",
            "metric_code": "LINE_1_OEE",
            "values": {
                "oee": 88.5,
                "avail": 92.0,
                "perf": 96.0,
                "qual": 99.8
            }
        }
    }
    client.publish(T_MOUNTER_MET, json.dumps(payload))
    print(f"📊 [Metrics] Sent: {payload['data']['metric_code']} OEE: {payload['data']['values']['oee']}%")

def main():
    parser = argparse.ArgumentParser(description="UNS Smart Factory Scenario Simulator")
    parser.add_argument("--scenario", type=str, choices=["telemetry", "status", "alarm", "event", "measurement", "metrics", "lifecycle"], required=True)
    parser.add_argument("--count", type=int, default=1, help="Number of times to run the scenario")
    parser.add_argument("--interval", type=float, default=2.0, help="Interval between logs in lifecycle mode")
    args = parser.parse_args()

    client = mqtt.Client(client_id=f"sim_{args.scenario}")
    try:
        client.connect(BROKER, PORT)
        client.loop_start()
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    print(f"🚀 Running Scenario: {args.scenario} (Count: {args.count})")

    for i in range(args.count):
        if args.scenario == "telemetry":
            publish_scenario_telemetry(client)
        elif args.scenario == "status":
            publish_scenario_status(client)
        elif args.scenario == "alarm":
            publish_scenario_alarm(client)
        elif args.scenario == "event":
            publish_scenario_event(client)
        elif args.scenario == "measurement":
            publish_scenario_measurement(client)
        elif args.scenario == "metrics":
            publish_scenario_metrics(client)
        elif args.scenario == "lifecycle":
            print("--- Starting Production Lifecycle ---")
            lot_id = f"LOT-{random.randint(1000, 9999)}"
            publish_scenario_telemetry(client)
            time.sleep(args.interval)
            publish_scenario_telemetry(client)
            time.sleep(args.interval)
            publish_scenario_event(client, "LOT_DISPATCHED", lot_id)
            time.sleep(args.interval)
            publish_scenario_event(client, "RECIPE_DOWNLOAD", lot_id)
            publish_scenario_telemetry(client)
            time.sleep(args.interval)
            publish_scenario_status(client, "PRD", "SET")
            time.sleep(args.interval)
            publish_scenario_event(client, "MATERIAL_LOAD", lot_id)
            time.sleep(args.interval)
            publish_scenario_event(client, "LOT_START", lot_id)
            time.sleep(args.interval)
            publish_scenario_status(client, "PRD", "RUN")
            time.sleep(args.interval)

            for b in range(1, 4):
                unit_id = f"PCB-{lot_id}-{b:03d}"
                publish_scenario_event(client, "UNIT_IN", lot_id, unit_id)
                publish_scenario_telemetry(client)
                time.sleep(args.interval/2)
                publish_scenario_event(client, "UNIT_OUT", lot_id, unit_id)
                publish_scenario_measurement(client)
                time.sleep(args.interval/2)
                publish_scenario_alarm(client)
                time.sleep(args.interval/2)
            
            publish_scenario_metrics(client)
            time.sleep(args.interval)
            publish_scenario_event(client, "LOT_END", lot_id)
            time.sleep(args.interval)
            publish_scenario_telemetry(client)
            time.sleep(args.interval)
            publish_scenario_status(client, "SBY", "IDL")
            publish_scenario_telemetry(client)
            time.sleep(args.interval)
            print("--- Lifecycle Completed ---")

        if i < args.count - 1:
            time.sleep(1)

    client.loop_stop()
    client.disconnect()
    print("🟢 Simulation finished.")

if __name__ == "__main__":
    main()
