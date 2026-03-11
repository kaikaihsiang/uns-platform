import json
import math
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
TOPIC = "TaiwanPrecision/Taoyuan/SMT_Line_1/SMT-Mounter-01/Telemetry"

client = mqtt.Client()
client.connect(BROKER, PORT)

print(f"Publishing Enterprise SMT Printer data to {TOPIC}...")

try:
    t = 0
    while True:
        # Generate some oscillating process data
        payload = {
            "_meta": {
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "temperature": round(25.0 + 5 * math.sin(t), 2),
            "pressure": round(2.0 + 0.2 * math.cos(t), 2),
            "recipe_name": "RECIPE-A" if random.random() > 0.05 else "RECIPE-B",
            "humidity": round(45.0 + 2 * random.random(), 1)
        }
        
        # Publish
        client.publish(TOPIC, json.dumps(payload))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Sent: {payload}")
        
        t += 0.5
        time.sleep(2)
        
except KeyboardInterrupt:
    print("\nStopped publishing.")
    client.disconnect()
