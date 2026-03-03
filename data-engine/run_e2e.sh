#!/bin/bash
# 確保在專案根目錄執行
cd "$(dirname "$0")/.."

echo "====================================================="
echo " UNS Data Engine - Automated E2E Verification"
echo "====================================================="

# 啟用虛擬環境
source .venv/bin/activate
export PYTHONPATH=$PYTHONPATH:$(pwd)/data-engine

echo "[1/3] Starting Data Engine in background..."
# 加上一個隨機 Client ID 避免與可能還在跑的其他 Data Engine 衝突
export MQTT_CLIENT_ID="uns-data-engine-test-$RANDOM"
python data-engine/main.py > /tmp/uns-e2e-data-engine.log 2>&1 &
DE_PID=$!

# 等待 Data Engine 啟動完成
sleep 3

echo "[2/3] Running E2E Verification Script..."
python data-engine/verify_e2e.py
RESULT=$?

echo "[3/3] Shutting down background Data Engine..."
kill -SIGTERM $DE_PID

if [ $RESULT -eq 0 ]; then
    echo -e "\n✅ All checks passed successfully!"
else
    echo -e "\n❌ Verification FAILED. Checking Data Engine logs for clues:\n"
    tail -n 15 /tmp/uns-e2e-data-engine.log
fi

exit $RESULT
