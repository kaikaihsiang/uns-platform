import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """
    驗證系統健康檢查端點。
    """
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data

@pytest.mark.asyncio
async def test_root_redirect(client: AsyncClient):
    """
    驗證根路徑是否正確（應回傳 404 或特定訊息，取決於 main.py 配置）。
    """
    response = await client.get("/")
    # 根據目前的 main.py，我們沒有定義 root，所以應該是 404
    assert response.status_code == 404
